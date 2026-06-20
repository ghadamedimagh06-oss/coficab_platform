# Coficab Platform → TMS-grade Roadmap

A gap analysis of what this platform does today versus what a production-grade
Transport Management System (TMS) needs. Priorities: **P0** = blocks "real,
trustworthy operations", **P1** = expected TMS capability, **P2** = differentiator.

> Status legend: ✅ done · 🟡 partial · ❌ missing

> **2026-06-13 — P0 backbone landed.** The "trustworthy TMS" core from the
> suggested order of attack is implemented & verified end-to-end against
> Postgres: (1) the **execution / ePOD loop** (`execution_service.py`,
> `/api/execution/*`, `livraison_preuve` proof table) advances
> plan→missions→demandes through to LIVREE, which makes **OTIF/OTD real**
> (`/api/metrics/kpi` now reads delivery actuals); (2) **Alembic** migrations
> (`backend/alembic/`) with a verified baseline; (3) **security** hardening
> (bcrypt direct, fail-fast secrets/DSN in production, gated dev auth bypass —
> `app/config.py`). Reproducible fleet seeding added to `seed_from_files.py`.
> Covered by `tests/test_execution_loop.py`. Remaining items below are the
> next P1/P2 layers.

---

## 1. Data & persistence
- 🟡 **Postgres is wired** (`backend/app/database.py`); master data seeded from files
  via `backend/scripts/seed_from_files.py` (clients, demandes, camions, chauffeurs,
  kpi_definition, admin user).
- ✅ **P0 — Schema migrations.** **Alembic** is wired (`backend/alembic/`, URL
  resolved from `DATABASE_URL` via `app.config`). Baseline `01f614faa2d0`
  reflects the full schema and applies cleanly to a fresh DB (the camions↔
  chauffeurs FK cycle is broken with deferred `create_foreign_key`). Existing
  DBs are reconciled with `alembic stamp head`. `create_all` is kept only for
  the SQLite test suite / offline mode. (clients.id manual-PK quirk still TODO.)
- ✅ **P0 — Plans are persisted & executed.** `/api/optimization/run`
  materialises `plan_version`/`plan_mission`/`mission_demande`; the new
  execution loop (`/api/execution/*`) then drives them through
  VALIDE→EXECUTE→CLOTURE with delivery confirmations. History/audit/KPIs now
  have a DB source of truth.
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
- ✅ **P0 — Electronic Proof of Delivery (ePOD).** `POST /api/execution/stops/
  {id}/confirm` records a `livraison_preuve` (signataire/photo/notes/on-time,
  full vs partial) and advances the demande to LIVREE; `/exception` captures
  refusals/no-shows as `evenement_alea` and cancels the stop. This is the input
  that turns KPIs into *actuals* (see §5). _Driver mobile UI still pending._
- ❌ **P1 — Driver mobile app**, geofenced arrival/departure, dynamic ETA.

## 5. KPIs: forecast → actuals  ← the "is the data real?" gap
- 🟡 Dashboard KPIs (OTIF/OTD/Load/Fuel) are **plan-derived forecasts**
  (`dashboard_service._finalize_kpis`), now consistent with the planning page
  (both use OR-Tools). A position only "misses" when left **unassigned**.
- ✅ `kpi_definition` seeded with authoritative thresholds for the 4 dashboard KPIs.
- ✅ **P0 — OTIF/OTD from real deliveries.** ePOD (§4) now writes
  `demandes_local.statut=LIVREE` + `livree_a_temps` + `quantite_livree_kg`, so
  `KpiService._compute_otif`/`_compute_otd` return real values. Verified live:
  `/api/metrics/kpi` reported OTIF 87.5% / OTD 79.3% from confirmed deliveries
  (was always `null`/forecast before).
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
- ✅ **P0 — Auth hardened.** Dropped the fragile `passlib` shim for direct
  `bcrypt` (`auth_service.hash_password`/`verify_password`). The anonymous→admin
  dev fallback is now gated by `app.config.dev_bypass_allowed()` — **disabled in
  production and whenever `REQUIRE_AUTH` is set** (401/403 instead).
- ✅ **P0 — Secrets fail-fast.** `app/config.py` resolves `JWT_SECRET` and
  `DATABASE_URL`: dev gets safe local defaults, but with `APP_ENV=production` the
  app **refuses to start** on a placeholder secret or a default-credential DSN.
  `.env.example` documents `APP_ENV`/`REQUIRE_AUTH`.
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
1. ✅ **P0 execution loop:** ePOD/delivery confirmation → advance
   `demandes_local` status → real OTIF/OTD (§4, §5). _Done 2026-06-13._
2. ✅ **P0 persistence & migrations:** Alembic + plans persisted/executed in
   `plan_mission`/`mission_demande` (§1). _Done 2026-06-13._
3. ✅ **P0 security:** bcrypt, gated dev fallback, fail-fast secrets/DSN (§10).
   _Done 2026-06-13._
4. **P1 tracking:** telematics/GPS + live ETA + driver app (§4).
5. **P1 fleet/maintenance, carrier/rate, billing** (§6–8).
6. **P1 observability + CI/CD + tests** so it can be operated, not just demoed (§11).
