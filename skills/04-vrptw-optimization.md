# 04 — VRPTW Optimization Engine

> Goal: turn pending `demandes_local` rows into a **candidate** `plan_version` (status `DRAFT`) made of `plan_mission` + `mission_demande` rows. The transport manager approves it in skill 05.

## KPI anchor
The objective function is the place where every KPI weight lives:

```
minimize:
   α · total_km                                    ← drives R5-10 (cost) and R4-13 (fuel)
 + β · expected_delay_penalty_minutes              ← drives R4-02 OTD and R4-06 OTIF
 + γ · (100 − load_efficiency_percent_average)     ← drives R4 Load Efficiency
 + δ · expected_premium_freight_eur                ← drives R4-02-PF and R4-03
 + ε · expected_fuel_litres_per_tkm                ← drives R4-13 directly
```

Defaults: `α=1.0, β=2.0, γ=1.5, δ=3.0, ε=1.0`. The admin UI exposes these sliders (skill 09).

---

## Keep it boring

Don't roll your own VRPTW. Use **Google OR-Tools `pywrapcp.RoutingModel`** — same path as your existing `vrptw_complete_optimizer.py`. Solver: PATH_CHEAPEST_ARC for initial, GUIDED_LOCAL_SEARCH for improvement. Time limit 60s for daily, 180s for weekly. That's enough.

Don't introduce ML. The spec explicitly says reinforcement learning is out of scope for v1.

---

## Inputs

From the DB at run time:
- `camions` where `status = 'DISPONIBLE'` → vehicle pool (capacity_kg, max_palettes, default speed=60 km/h)
- `chauffeurs` where `status = 'ACTIF'` and on shift that day → driver pool
- `clients` for coordinates and time windows
- `demandes_local` where `statut = 'NOUVELLE'` and `date_livraison BETWEEN plan_start AND plan_end`
- `kpi_definition` (to read α/β/γ/δ/ε weights — see end of this file)

---

## Distance & time matrix

Two options, both acceptable:

**Option A — Haversine** (zero cost, ~OK accuracy for daily planning):
```python
import math
def haversine_km(a, b):
    lat1, lon1 = map(math.radians, a); lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1; dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * 6371 * math.asin(math.sqrt(h))
```

**Option B — OSRM** (free, self-hostable). Recommended once the system runs in real conditions. Set up later, not now.

For v1, ship Haversine. Cache the matrix in memory per optimizer run; rebuild if `clients` table changes.

---

## File: `backend/app/services/vrptw_optimizer.py`

(Renamed from `vrptw_complete_optimizer.py`. Archive the existing file as `_archive/` if you want to preserve it.)

```python
import logging
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from sqlalchemy.orm import Session

from app.models.camion import Camion, CamionStatus
from app.models.chauffeur import Chauffeur, ChauffeurStatus
from app.models.client import Client
from app.models.demande import DemandeLocal, StatutDemande
from app.models.plan import PlanVersion, PlanMission, MissionDemande, StatutPlan, StatutMission, ModeMission, Periode

log = logging.getLogger(__name__)

@dataclass
class OptimizerWeights:
    alpha: float = 1.0   # distance
    beta: float = 2.0    # delay
    gamma: float = 1.5   # underutilization
    delta: float = 3.0   # premium freight
    epsilon: float = 1.0 # fuel

@dataclass
class OptimizerConfig:
    time_limit_sec: int = 60
    speed_kmh: int = 60
    service_time_min: int = 15           # unloading time at each stop
    work_window_hours: int = 10          # max shift length
    depot_lat: float
    depot_lon: float
    weights: OptimizerWeights = OptimizerWeights()

class VrptwOptimizer:
    def __init__(self, db: Session, cfg: OptimizerConfig):
        self.db = db
        self.cfg = cfg

    def plan(self, day: date) -> PlanVersion:
        trucks   = self._available_trucks()
        drivers  = self._available_drivers(day)
        demandes = self._pending_demandes(day)
        if not demandes:
            raise ValueError("no pending demandes for this day")

        nodes, demande_index = self._build_nodes(demandes)
        dist_m, time_m = self._build_matrices(nodes)

        manager = pywrapcp.RoutingIndexManager(len(nodes), len(trucks), 0)
        routing = pywrapcp.RoutingModel(manager)

        # ----- cost = α·distance + ε·fuel
        def cost_cb(from_idx, to_idx):
            i = manager.IndexToNode(from_idx); j = manager.IndexToNode(to_idx)
            km = dist_m[i][j]
            fuel_l = km * 0.30                              # 30L/100km baseline
            return int(self.cfg.weights.alpha * km * 100
                     + self.cfg.weights.epsilon * fuel_l * 10)
        cost_index = routing.RegisterTransitCallback(cost_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(cost_index)

        # ----- capacity constraint (kg)
        def demand_cb(idx):
            node = manager.IndexToNode(idx)
            return int(nodes[node]["kg"])
        dem_index = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            dem_index, 0,
            [int(t.capacite_kg) for t in trucks],
            True, "Capacity"
        )

        # ----- time dimension with windows
        def time_cb(from_idx, to_idx):
            i = manager.IndexToNode(from_idx); j = manager.IndexToNode(to_idx)
            travel = time_m[i][j]
            service = 0 if j == 0 else self.cfg.service_time_min
            return int(travel + service)
        time_index = routing.RegisterTransitCallback(time_cb)
        routing.AddDimension(time_index, 30, self.cfg.work_window_hours * 60, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        for node_idx, node in enumerate(nodes):
            if node_idx == 0: continue
            start_min, end_min = node["window"]
            time_dim.CumulVar(manager.NodeToIndex(node_idx)).SetRange(start_min, end_min)

        # ----- search
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.FromSeconds(self.cfg.time_limit_sec)

        solution = routing.SolveWithParameters(params)
        if solution is None:
            raise RuntimeError("VRPTW solver returned no solution")

        return self._materialize(day, trucks, drivers, demandes, manager, routing, solution, nodes, demande_index)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------
    def _available_trucks(self) -> list[Camion]:
        return self.db.query(Camion).filter(Camion.status == CamionStatus.DISPONIBLE).all()

    def _available_drivers(self, day: date) -> list[Chauffeur]:
        return self.db.query(Chauffeur).filter(Chauffeur.status == ChauffeurStatus.ACTIF).all()

    def _pending_demandes(self, day: date) -> list[DemandeLocal]:
        return (self.db.query(DemandeLocal)
                       .filter(DemandeLocal.date_livraison == day,
                               DemandeLocal.statut == StatutDemande.NOUVELLE)
                       .all())

    def _build_nodes(self, demandes):
        # node 0 is the depot, nodes 1..N are demandes
        nodes = [{"lat": self.cfg.depot_lat, "lon": self.cfg.depot_lon,
                  "kg": 0, "window": (0, self.cfg.work_window_hours * 60)}]
        demande_index = {}
        for d in demandes:
            c: Client = d.client
            start = self._minutes(c.fenetre_ouverture) if c.fenetre_ouverture else 0
            end   = self._minutes(c.fenetre_fermeture) if c.fenetre_fermeture else self.cfg.work_window_hours * 60
            nodes.append({"lat": float(c.latitude or 0), "lon": float(c.longitude or 0),
                          "kg": float(d.quantite_kg), "window": (start, end)})
            demande_index[len(nodes) - 1] = d
        return nodes, demande_index

    def _build_matrices(self, nodes):
        from math import radians, sin, cos, asin, sqrt
        def km(a, b):
            la1, lo1, la2, lo2 = map(radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
            dlat = la2 - la1; dlon = lo2 - lo1
            h = sin(dlat/2)**2 + cos(la1)*cos(la2)*sin(dlon/2)**2
            return 2 * 6371 * asin(sqrt(h))
        N = len(nodes); dist = [[0]*N for _ in range(N)]; time = [[0]*N for _ in range(N)]
        for i in range(N):
            for j in range(N):
                if i == j: continue
                d = km(nodes[i], nodes[j])
                dist[i][j] = d
                time[i][j] = int(round(d / self.cfg.speed_kmh * 60))   # minutes
        return dist, time

    @staticmethod
    def _minutes(t) -> int:
        return t.hour * 60 + t.minute

    # ----------------------------------------------------------------
    # Materialize solution → DB rows (DRAFT)
    # ----------------------------------------------------------------
    def _materialize(self, day, trucks, drivers, demandes, manager, routing, solution, nodes, demande_index):
        last_plan = self.db.query(PlanVersion).order_by(PlanVersion.plan_id.desc()).first()
        plan_id = (last_plan.plan_id + 1) if last_plan else 1
        version = PlanVersion(
            plan_id=plan_id, version_number=1,
            periode=Periode.JOUR, date_debut=day, date_fin=day,
            statut_plan=StatutPlan.DRAFT,
            commentaire="generated by VrptwOptimizer",
        )
        self.db.add(version); self.db.flush()

        for vehicle_id, truck in enumerate(trucks):
            index = routing.Start(vehicle_id)
            stops, total_kg, total_km = [], 0, 0
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index); next_index = solution.Value(routing.NextVar(index))
                if node != 0:
                    d = demande_index[node]
                    stops.append((d, node))
                    total_kg += float(d.quantite_kg)
                if next_index != index:
                    nn = manager.IndexToNode(next_index)
                    total_km += self._build_matrices(nodes)[0][node][nn]
                index = next_index
            if not stops:
                continue
            driver = drivers[vehicle_id % len(drivers)]
            mission = PlanMission(
                plan_version_id=version.id,
                camion_id=truck.id,
                chauffeur_id=driver.id,
                date_mission=day,
                statut=StatutMission.PLANIFIEE,
                mode=ModeMission.NORMAL,
                km_parcourus=total_km,
                charge_kg=total_kg,
                load_eff_kg_pct=round(total_kg / float(truck.capacite_kg) * 100, 2),
            )
            self.db.add(mission); self.db.flush()
            for order, (demande, _node) in enumerate(stops, start=1):
                self.db.add(MissionDemande(
                    mission_id=mission.id,
                    demande_id=demande.id,
                    ordre_livraison=order,
                ))
                demande.statut = StatutDemande.PLANIFIEE
        self.db.commit()
        return version
```

> Notes
> - Computes Haversine matrix twice (once for solver, once for materialize). Cache it if your fleet is large; for ≤ 50 stops the cost is negligible.
> - Driver assignment is round-robin — replace with default-truck assignment from `chauffeurs.camion_defaut_id` once data is reliable.

---

## When the optimizer runs

| Trigger | Frequency | Source |
|---|---|---|
| Excel file dropped for tomorrow | once on ingestion success | `IngestionService` callback |
| Scheduled daily run | every day 06:00 local | APScheduler (skill 00) |
| Manual "Re-optimize" button | on demand | `POST /api/optimization/run` |

The result is always a **new `plan_version` with `statut_plan = DRAFT`**. It never overwrites a validated plan; a new version is created.

---

## API endpoints

```
POST /api/optimization/run             { day: "2026-05-25", weights?: {...} }
  → returns the new plan_version_id

GET  /api/optimization/plan/{id}       → plan_version + missions + stops
GET  /api/optimization/plan/{id}/kpis  → preview of expected KPIs for this plan
                                        (load eff %, total km, premium count, …)
POST /api/optimization/weights         (admin) update α/β/γ/δ/ε defaults
```

The KPI-preview endpoint is critical: skill 05's "real-time impact" needs it.

---

## Verification

Insert 5 demandes for 5 different clients with known coordinates. Run the optimizer with default weights. Check:

1. A new `plan_version` row exists with `statut_plan='DRAFT'`.
2. Sum of `mission_demande.ordre_livraison` across all missions covers all 5 demandes (no orphans).
3. For each mission, `charge_kg ≤ camion.capacite_kg` (capacity respected).
4. `load_eff_kg_pct ≥ 50%` on average for reasonable demand density.
5. `/api/optimization/plan/{id}/kpis` returns expected R4-02, R4-13, R4 values close to historical baseline.
