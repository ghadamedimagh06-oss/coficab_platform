# Coficab Platform → TMS-grade Roadmap

A gap analysis of what this platform does today versus what a production-grade
Transport Management System (TMS) needs. Priorities: **P0** = blocks "real,
trustworthy operations", **P1** = expected TMS capability, **P2** = differentiator.

> Status legend: ✅ done · 🟡 partial · ❌ missing

---

## 1. Data & persistence
- 🟡 **Postgres is wired** (`backend/app/database.py`); master data seeded from files
  via `backend/scripts/seed_from_files.py` (clients, demandes, camions, chauffeurs,
  kpi_definition, admin user).
- ❌ **P0 — Schema migrations.** Tables are created with `Base.metadata.create_all`
  (no versioning). Add **Alembic** so schema changes are reproducible and the
  `clients.id` "manual PK / no sequence" quirk is fixed deliberately, not by hand.
- ❌ **P0 — Plans are not persisted.** `plan_mission`, `mission_demande`,
  `plan_version`, `planning_versions` are empty; every screen rebuilds the plan
  in-memory each request. Persist each generated/edited plan so history, audit,
  and KPIs have a source of truth.
- 🟡 Idempotent seed exists, but there's **no real order-intake pipeline** beyond
  the weekly Excel ingester (`ingestion_service.py`).

## 2. Order / demand management
- 🟡 Weekly Excel → `demandes_local` (status `NOUVELLE`). Good enough for forecast.
- ❌ **P1 — Order lifecycle.** Statuses exist (`NOUVELLE→PLANIFIEE→EN_COURS→LIVREE`)
  but nothing advances them. Need a state machine driven by planning + execution.
- ❌ **P1 — Live intake** (REST/EDI/API), customer order portal, order amendments.

## 3. Planning & optimization  ← current strength
- ✅ OR-Tools VRPTW with time windows, capacity (positions + kg), same-day splits,
  parallel-truck objective, real OSRM road distances, rented-truck fallback.
- ❌ **P1 — Driver legal compliance (HOS):** driving-time / rest rules, shift limits.
- ❌ **P1 — Multi-day & rolling horizon** planning (today it's single-day).
- ❌ **P2 — Dynamic re-optimization** when an incident/delay/cancellation lands.
- ❌ **P2 — Multi-depot, backhauls, pickup+delivery, carrier mix.**
- ❌ **P1 — Scenario comparison.** Let dispatchers compare side-by-side:
  **current (as-dispatched) vs optimized vs last-week**, with deltas on cost, km,
  truck count, OTIF/load and unassigned. Needs persisted plans (§1) to diff
  against, plus a "what-if" run that doesn't overwrite the live plan.

## 3b. Geographic routing & distances
- 🟡 **OSRM is integrated** for route polylines/road distances
  (`geo_service.road_km_matrix`, used by the planner and the map).
- ❌ **P1 — Remove remaining synthetic distance estimates.** Some paths still fall
  back to straight-line/`avg_speed_kmh` time and table `km` (e.g. depot return-leg
  approximations in `dashboard_service.plan_metrics`, the client-directory `km`
  column). Route **every** leg through real geographic routing.
- ❌ **P1 — Pluggable routing provider.** Abstract the engine so OSRM / **Valhalla**
  / **Google Maps / Mapbox** are swappable, with live traffic-aware ETAs and a
  cached fallback for offline runs.

## 4. Execution, tracking & ePOD  ← biggest missing pillar
- ❌ **P0 — No real-time tracking.** `transport_tracking` is empty; the map plots
  *planned* stops, not live vehicle GPS. Integrate telematics/GPS.
- ❌ **P0 — Electronic Proof of Delivery (ePOD).** No delivery confirmation,
  signature/photo capture, or exception capture. This is the missing input that
  makes KPIs *actuals* instead of *forecast* (see §5).
- ❌ **P1 — Driver mobile app**, geofenced arrival/departure, dynamic ETA.

## 5. KPIs: forecast → actuals  ← the "is the data real?" gap
- 🟡 Dashboard KPIs (OTIF/OTD/Load/Fuel) are **plan-derived forecasts**
  (`dashboard_service._finalize_kpis`), now consistent with the planning page
  (both use OR-Tools). A position only "misses" when left **unassigned**.
- ✅ `kpi_definition` seeded with authoritative thresholds for the 4 dashboard KPIs.
- ❌ **P0 — OTIF/OTD from real deliveries.** `KpiService._compute_otif` needs
  `demandes_local.statut=LIVREE` + `livree_a_temps` + `quantite_livree_kg`, which
  only exist once ePOD (§4) confirms deliveries. Until then "real OTIF" is impossible.
- ❌ **P1 — KPI snapshots.** `kpi_journalier`/`kpi_mensuel` empty; `recompute_kpis.py`
  can't produce values until `plan_mission`/`livraisons` are populated.
- ❌ **P1 — The other 4 KPIs** (Premium Freight Cost/Occurrences, Logistics Cost,
  Customer Incidents) are *defined* but have **no colour bands and no compute path**
  wired to the dashboard.

## 6. Fleet & resource management
- 🟡 `camions` + `chauffeurs` seeded and served by `/api/fleet/*`.
- ❌ **P1 — Maintenance scheduling**, vehicle availability calendar, telematics
  (odometer/fuel), driver licence expiry & certification tracking, fuel cards.

## 7. Carrier & freight (3PL) management
- ❌ **P1 — Rate/contract management**, carrier selection & tendering, freight
  audit & settlement. Premium-freight (`R4-02-PF`) is named but has no engine.

## 8. Cost, billing & settlement
- 🟡 Planner computes an operating-cost breakdown (`_cost_breakdown`, TND).
- ❌ **P1 — Freight invoicing/billing**, accessorials, cost allocation per
  client/order, margin reporting.

## 9. Integrations
- ✅ OSRM for routing.
- ❌ **P1 — ERP (SAP) / WMS / EDI** for orders, inventory, and invoicing.
- ❌ **P2 — Customs/export handling** (today export sites are simply dropped as
  "not a domestic truck run").

## 10. Security, auth & compliance  ← needs hardening before any real use
- ❌ **P0 — Auth is broken/bypassable.** `passlib 1.7.4` is incompatible with
  `bcrypt>=4.1` in this venv (hash/verify raise); `auth_service` also has a **dev
  fallback that returns a fake admin when no token is sent**. Fix the passlib/bcrypt
  pin and remove/guard the fallback behind an explicit env flag.
- ❌ **P0 — Secrets.** Default DB URL with `postgres:postgres` is hardcoded; no
  `.env`, no secret management. JWT signing key handling needs review.
- ❌ **P1 — RBAC enforcement** (roles exist on `users` but aren't enforced),
  audit log, per-tenant/plant isolation.

## 11. Observability & reliability
- ❌ **P1 — Structured logging, metrics, tracing, alerting**, real health/readiness
  probes.
- ❌ **P1 — Tests & CI/CD.** There are tests under `backend/tests/`, but new data
  paths (seeding, DB-backed KPIs) are uncovered; no CI pipeline or containerization
  (Dockerfile/compose) for reproducible deploys.

---

## Suggested order of attack (to reach a *trustworthy* TMS)
1. **P0 execution loop:** ePOD/delivery confirmation → populate `livraisons` &
   advance `demandes_local` status → real OTIF/OTD (§4, §5).
2. **P0 persistence & migrations:** Alembic + persist plans to `plan_mission` (§1).
3. **P0 security:** fix auth, remove dev fallback, move secrets to env (§10).
4. **P1 tracking:** telematics/GPS + live ETA + driver app (§4).
5. **P1 fleet/maintenance, carrier/rate, billing** (§6–8).
6. **P1 observability + CI/CD + tests** so it can be operated, not just demoed (§11).
