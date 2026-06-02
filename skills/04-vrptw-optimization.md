# 04 — VRPTW Optimization Engine

> Goal: turn pending `demandes_local` rows into a **candidate** `plan_version` (status `DRAFT`) made of `plan_mission` + `mission_demande` rows. The transport manager approves it in skill 05.

---

## Core design principles

### 1. Geographic zone clustering (K-means++)

Before routing, all delivery points are partitioned into **k geographic zones** where k = number of available trucks.  Each zone is served by exactly one truck.

```
cluster_zones(latlons, k) → k lists of delivery indices
```

Implemented in `vrptw_optimizer.py::cluster_zones()` using **K-means++ initialisation** (spread initial centroids for better zone separation) followed by Lloyd's iterations (max 30).

Why this matters:
- Routes are **spatially compact** — no truck crosses the city to reach an isolated stop.
- **No road segment is traversed by more than one truck**: since every arc (i→j) belongs to exactly one zone's route, it cannot appear in any other vehicle's route across the full plan.  This eliminates redundant road usage.
- Cluster assignment is deterministic (seeded RNG) for reproducible plans.

### 2. Capacity rebalancing after clustering

If a zone's total weight exceeds its truck's capacity, the **heaviest overflowing node is moved to the least-loaded zone that still has room**.

```
_rebalance_for_capacity(clusters, kg_per_point, capacities_kg)
    → (rebalanced_clusters, unassigned_positions)
```

Nodes that cannot fit any truck are logged as warnings and excluded from the plan.

### 3. Per-zone single-vehicle VRPTW

Each zone is solved independently as a **single-vehicle VRPTW** using OR-Tools `pywrapcp.RoutingModel` with one vehicle.  Single-vehicle subproblems are smaller and faster than the full multi-vehicle problem, and the zone isolation already handles the inter-vehicle constraint.

Fallback: **nearest-neighbour greedy** when OR-Tools is unavailable.

---

## KPI anchor — objective function

The per-zone arc cost (passed to OR-Tools) is:

```
cost(i→j) = α · km(i,j) · 100  +  ε · fuel_litres(i,j) · 10
```

The full plan objective (across all zones) maps to:

```
minimize:
   α · total_km                           ← drives R5-10 (cost) and R4-13 (fuel)
 + β · expected_delay_penalty_minutes     ← drives R4-02 OTD and R4-06 OTIF
 + γ · (100 − load_efficiency_avg)        ← drives R4 Load Efficiency
 + δ · expected_premium_freight_eur       ← drives R4-02-PF and R4-03
 + ε · expected_fuel_litres_per_tkm       ← drives R4-13 directly
```

Defaults: `α=1.0, β=2.0, γ=1.5, δ=3.0, ε=1.0`. The admin UI exposes these sliders (skill 09).

---

## Inputs

From the DB at run time:
- `camions` where `status = 'DISPONIBLE'` → vehicle pool (capacite_kg, max_palettes, consommation_base_l_100km)
- `chauffeurs` where `status = 'ACTIF'` → driver pool (preferred driver from `camion.chauffeur_defaut_id`)
- `clients` for coordinates (latitude, longitude) and time windows (fenetre_ouverture, fenetre_fermeture)
- `demandes_local` where `statut = 'NOUVELLE'` and `date_livraison = plan_day`

---

## Distance matrix

Haversine formula — implemented in `_haversine_km()`.  The matrix is built once per optimizer run and reused by the per-zone solvers and the materialize step.

OSRM can replace haversine in production; change `_build_dist_matrix()` in `VrptwOptimizer`.

---

## Algorithm steps

```
1. Load trucks, drivers, demandes from DB
2. Build node list: node 0 = depot, nodes 1..N = demandes (with client lat/lon + time window)
3. cluster_zones(latlons, k=len(trucks))
4. _rebalance_for_capacity(clusters, kg_per_delivery, truck_capacities)
5. Sort: assign heaviest zone → largest truck (by capacite_kg)
6. For each (truck, zone):
     a. _solve_zone(nodes, zone_indices, truck, dist_m)
        → OR-Tools single-vehicle VRPTW, or greedy fallback
     b. Compute total_km, total_kg, load_eff_pct, fuel_l, cout_transport_eur
     c. INSERT PlanMission
     d. INSERT MissionDemande for each stop (with ordre_livraison)
     e. UPDATE demande.statut → PLANIFIEE
7. COMMIT → PlanVersion(DRAFT) returned
```

---

## Files

| File | Role |
|---|---|
| `backend/app/services/vrptw_optimizer.py` | `VrptwOptimizer` (DB-aware) + `VRPTWOptimizer` (dict-based legacy) + `cluster_zones()` + `_rebalance_for_capacity()` |
| `backend/app/routes/optimization.py` | API endpoints (see below) |
| `backend/app/agents/optimizer.py` | APScheduler job wrapper — calls `VrptwOptimizer.plan()` at 06:00 |

`VRPTWOptimizer` (dict-based) is kept for the frontend planning UI (`/api/optimization/planning/generate`).  It also uses `cluster_zones()` and enforces zone isolation via `routing.SetAllowedVehiclesForIndex()` in OR-Tools.

---

## API endpoints

```
POST /api/optimization/run
  Body: { day: "2026-05-25", depot_lat?, depot_lon?, time_limit_sec?, weights?: {α,β,γ,δ,ε} }
  Returns: { plan_version_id, plan_id, status, date, commentaire }

GET  /api/optimization/plan/{plan_version_id}
  Returns: plan_version + missions[] + stops[] per mission

GET  /api/optimization/plan/{plan_version_id}/kpis
  Returns: preview KPIs computed from DRAFT missions:
    R4  load efficiency %
    R4-13 fuel efficiency mL/T.km
    R5-10 logistics cost €/T
    R4-03 premium freight count

POST /api/optimization/weights
  Body: { alpha, beta, gamma, delta, epsilon }
  Note: weights are per-request for now; pass them in the next /run call.

POST /api/optimization/planning/generate    ← legacy frontend UI
  Body: { deliveries, trucks, current_routes }
  Returns: { routes, unassigned, costs, suggestions, metrics }
```

---

## When the optimizer runs

| Trigger | Frequency | Source |
|---|---|---|
| Excel file ingested for tomorrow | once on ingestion success | `IngestionService` callback |
| Scheduled daily run | every day 06:00 local | APScheduler → `agents/optimizer.py::run()` |
| Manual "Re-optimize" button | on demand | `POST /api/optimization/run` |

The result is always a **new `plan_version` with `statut_plan = DRAFT`**.  A validated plan is never overwritten; a new version is created.

---

## Verification checklist

1. Insert ≥ 5 demandes for clients in at least 2 distinct geographic zones.
2. `POST /api/optimization/run { day: "..." }` → returns a `plan_version_id`.
3. `GET /api/optimization/plan/{id}` → missions cover all 5 demandes (no orphans).
4. For each mission, `charge_kg ≤ camion.capacite_kg` (capacity respected).
5. No two missions share an arc: for every pair of missions, their stop sequences should not share the same (clientA → clientB) arc.
6. `GET /api/optimization/plan/{id}/kpis` → `load_eff_pct ≥ 50%` average for reasonable demand density.
7. Run with 1 truck → all stops in one route, full greedy order, no clustering errors.
8. Run with more trucks than deliveries → some missions have 1 stop; no crash.
