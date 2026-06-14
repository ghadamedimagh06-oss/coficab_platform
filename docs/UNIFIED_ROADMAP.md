# COFICAB Platform — UNIFIED ROADMAP (the build plan)

> **This is the authoritative plan.** It synthesizes `MASTER_ROADMAP.md` (verified, focused) and
> `COMPREHENSIVE_AUDIT_AND_ROADMAP.md` (broad, but partly unverified). Every item here has a
> **verification status**. We build features end-to-end, fully working, with tests — and tick the boxes as we land them.
>
> Legend — Effort: **S** (<½ day) · **M** (1–2 days) · **L** (3–5 days) · **XL** (1–2 weeks).
> Status: ✅ done · 🔄 in progress · ⬜ todo · ❌ rejected (false finding) · 🔬 needs verification.

---

## 0. Reconciliation — what the two source plans got right & wrong

**Both agreed (verified TRUE, kept):**
- Hardcoded path in `backend/app/routes/data.py:28` (only there).
- Copilot doc drift: README/memory say Claude; code uses Groq/Llama-3.3-70B.
- Silent mock fallback + hardcoded frontend KPIs.
- Three overlapping optimizers; only `DailyPlanBuilder._solve_global_vrptw` is the good one.
- Two KPI sources (`/api/metrics/kpi` vs `/api/planning/daily/dashboard`).
- Default role = `admin` on missing claim (`auth_service.py:65`, `auth.py:93`).
- `tsconfig.json:11` `strict: false`.
- Excel re-parsed per request.

**Comprehensive doc — REJECTED as false (do NOT spend time on):**
- ❌ **I1 CORS `["*"]`** — actually a localhost whitelist + regex in `main.py`. Already safe.
- ❌ **I3 SQL injection** — zero raw SQL string-building; all SQLAlchemy ORM. Already safe.
- ❌ **F3 `.env` not gitignored** — it is (`.gitignore:49-51`). Already safe.
- ❌ **A1 path in `optimization.py:28`** — that line is `EXPORT_DIR`, not a hardcoded user path.
- ⚠️ **A12 bare excepts "everywhere"** — exactly ONE (`excel_watcher.py:296`). Fix that one.
- ⚠️ Many E/H/J/K items are generic boilerplate with unverified file refs — treat as *ideas*, verify before doing.

---

## WAVE 0 — Earn Trust (verified critical fixes) — ✅ COMPLETE (pytest green)

- [x] **W0.1 — Remove hardcoded path** (`data.py:28`). Env-driven via `_resolve_weekly_planning_file()`: `WEEKLY_PLANNING_FILE_PATH` → canonical repo file → newest `*.xlsx`. **(S)**
- [x] **W0.2 — Fix copilot doc drift.** README "Dispatch Copilot (Optiroute)" + tech-stack row + `.env.example` + `dispatch-copilot` memory → Groq/Llama (real provider). **(S)**
- [x] **W0.3 — Default role `viewer`, not `admin`** (`auth_service.py` ×2, `auth.py` ×4). **(S)**
- [x] **W0.4 — Fix the one bare except** (`excel_watcher.py:296`) → rollback + logged warning. **(S)**
- [x] **W0.5 — "DEMO DATA" signal.** `/api/data/source-status` endpoint + `used_mock` always present + global `DemoDataBanner` mounted in `AppShell`. **(M)**
- [x] **W0.6 — Repo hygiene.** Moved `_diag_fleet.py` → `backend/scripts/diag_fleet.py`. **(S)**
- [x] **W0.7 — Fixed pre-existing failing test** (`test_no_trip_exceeds_truck_capacity_or_working_hours`): aligned to the documented depart-by-18:00 contract (evening returns allowed). Whole suite now green (pytest exit 0).

## WAVE 1 — One Brain (unify + correctness)

- [ ] **W1.1 — Single optimizer.** Route all planning through the unified VRPTW; deprecate the legacy dict/DB optimizers (keep thin shims to avoid import breaks, mark deprecated). **(L)**
- [x] **W1.2 — One KPI source of truth.** ✅ DONE & tested. `/api/metrics/kpi` now prefers ERD snapshots but falls back to LIVE plan-derived KPIs (`dashboard_service.plan_kpis`) — the same source the dashboard uses — so the cards are never empty before snapshots are computed. Returns a `source` field (`snapshots`|`live_plan`) and adds a CO₂-Saved card. Cached (120s TTL). `tests/test_metrics_kpi.py` (2 tests).
- [x] **W1.3 — Excel parse cache.** ✅ DONE & tested. `PlanningService.parse_weekly_planning` now serves from a module-level cache keyed by (path, mtime_ns, size); returns deep copies so callers can mutate freely; auto-invalidates on any workbook edit. Benefits every caller (`/transports`, the plan builder, the watcher). Measured 159 ms → 0 ms on repeat parse. `tests/test_parse_cache.py` (3 tests).
- [x] **W1.4 — Volume / m³ capacity dimension.** ✅ DONE & tested. Volume is now a third, independent capacity dimension alongside positions and gross kg. Each truck declares `capacity_m3` (40 m³ rigids, 85–90 m³ semis); each delivery's volume is its explicit workbook m³ (`volume_m3`/`cbm`/…) or, absent that, positions × `m3_per_position` (1.8). Wired through the **global VRPTW** (a scaled "Volume" capacity dimension), `_feasible_trucks`, the hard-capacity prefilter (a load that cubes out the biggest truck is dropped with a volume reason), the heuristic scheduler & overflow rescue, zone assignment, splits (volume divides proportionally), and reporting (`capacity_m3` per truck, `volume_m3` per stop, `summary.total_volume_m3`, volume-aware under-utilisation). Safe **no-op** for any fleet that doesn't declare `capacity_m3` and **inert** on the position-only workbook (deck headroom set so derived volume never binds), so zero behaviour change today while being correct the moment real reel volumes arrive. Frontend `TruckLane` shows m³ capacity + used m³. `tests/test_volume_dimension.py` (14 tests). **(M)**

## WAVE 2 — 🏆 Flagship features (the "wooow")

- [x] **W2.1 — C3 Carbon & ESG Optimizer.** ✅ DONE & tested. CO₂ factor in `CostConfig`; `objective` modes (green/balanced/fast) drive the makespan coefficient; per-plan `sustainability` block (CO₂ emitted/saved vs unconsolidated baseline, fuel, trees/car equivalents); `POST /api/planning/daily/pareto` (frontier + recommendations + full plans) and `GET /api/planning/daily/esg-report`; frontend `SustainabilityPanel` (headline cards + objective compare + apply + JSON export) mounted on generated-daily-planning; `tests/test_sustainability.py` (8 tests). Backend pytest green; frontend prod build green.
- [x] **W2.2 — C10 Stress-Test Scenario Lab.** ✅ DONE & tested. `demand_multiplier` knob in the builder; `POST /api/planning/daily/stress-test` (baseline + scenario battery: lose biggest/2-biggest truck, +20%/+30% volume, no rental; per-scenario served %, unassigned, cost/CO₂ deltas, rental forced, finish time); frontend `StressTestPanel` (comparison table with colour-coded deltas) on generated-daily-planning; `tests/test_stress_test.py` (4 tests). Backend pytest green; frontend prod build green.
- [x] **W2.3 — C2 Monte-Carlo Plan Confidence.** ✅ DONE & tested. `simulation_service.simulate_plan` replays a plan 500× under lognormal travel/service noise + rare disruption spikes; reports expected OTIF, reliability (% days ≥ target OTIF), perfect-day %, finish P50/P90/worst, and ranked fragile stops (seeded/deterministic). `POST /api/planning/daily/confidence` (simulates an inline plan or builds one); frontend `ConfidencePanel` (OTIF gauge + finish spread + fragile-stop bars) on generated-daily-planning; `tests/test_confidence.py` (6 tests).
- [x] **W2.4 — C1 Self-Healing Replan.** ✅ DONE & tested. `DailyPlanBuilder.replan(day, deliveries)` re-optimises an explicit residual delivery set on a (reduced) fleet without touching the workbook/splitting. `POST /api/planning/daily/replan` takes the current plan + `disrupted_truck_ids` + `completed_stop_ids`, re-solves the undelivered stops on the remaining fleet, and returns the new plan + a diff (reassignments, newly-unassigned, recovered, cost/CO₂ deltas). Frontend `DisruptionPanel` (break trucks → review diff → one-click Apply) on generated-daily-planning; `tests/test_replan.py` (5 tests).
- [x] **W2.5 — C8 Explainable routing.** ✅ DONE & tested. `POST /api/planning/daily/explain` returns a grounded, plain-language rationale for a truck's route (PER-TRIP peak utilisation, binding constraint, single-feasible & hard-window stops, total km) + a right-sizing counterfactual + per-stop reasoning — all from the plan, no re-solve. Frontend `ExplainPanel` (truck picker → rationale + facts grid) on generated-daily-planning; `tests/test_explain.py` (3 tests, incl. a per-trip-utilisation invariant guarding the daily-sum bug).

## WAVE 3 — Smart & Real

- [ ] **W3.1 — C4 Agentic copilot write-tools** (propose split / reassign / replan) with human approval. **(L)**
- [x] **W3.2 — C6 Live control-tower map + geofence predicted-late alerts.** ✅ DONE & tested. `services/control_tower.py::live_snapshot(plan, now_min, delays)` turns a static plan into a LIVE picture with no GPS feed: it interpolates each truck's current position along its route (depot→stops→depot) segment-by-segment from the plan's depart/arrival/return times, classifies live state (pre-dispatch / en-route / at-stop / reloading / returning / completed), and raises predicted-late / geofence alerts for any stop whose projected arrival (after an optional injected per-truck delay) misses its hard delivery window. `POST /api/planning/daily/control-tower` (inline plan or builds one; `as_of` + `delays`). Frontend `ControlTowerPanel` (clock scrubber, fleet roll-up, delay-injection chips, ranked alert list, state legend) + `ControlTowerMap` (Leaflet: dimmed routes, live colour-coded truck markers, red at-risk drops) mounted on generated-daily-planning. `tests/test_control_tower.py` (14 tests, fully deterministic). **(L)**
- [x] **W3.3 — C9 One-click executive report.** ✅ DONE (frontend). `components/planning/executiveReport.js` builds a polished one-page **Operations & Sustainability board report** (ops KPIs, CO₂ saved + equivalences, optional confidence, fleet table) from the plan + `/esg-report` and opens it print-ready (browser Save-as-PDF). "Board report (PDF)" button in `SustainabilityPanel`.
- [ ] **W3.4 — C5 Predictive ETA & demand forecasting** (close the planned-vs-actual loop). **(XL)**
- [ ] **W3.5 — C7 WhatsApp driver channel + ePOD.** **(L)**

## WAVE 4 — Hardening (verified subset of E–K)

- [x] **W4.1 — DB indexes.** ✅ DONE & tested. `index=True` on the hot FK/filter columns: `plan_mission.(plan_version_id,date_mission)`, `mission_demande.(mission_id,demande_id)`, `demandes_local.(client_id,date_livraison)`, `livraisons.(delivery_day,status)`, `kpi_journalier.(kpi_def_id,date_mesure)`. `tests/test_db_indexes.py` (10 parametrised checks via schema introspection). Note: an Alembic migration is still needed to add these to an EXISTING Postgres DB (create_all covers fresh DBs).
- [x] **W4.2 — Structured logging + `/metrics`.** ✅ DONE & tested. Dependency-free `app/observability.py`: an in-process metrics registry + middleware that times every request and records request/error counts, a latency histogram and an in-flight gauge — keyed by the ROUTE TEMPLATE (not the raw URL) so cardinality stays bounded. Exposed at `/metrics` (Prometheus text exposition) and `/metrics.json`. Because solver/LLM work runs inside the handler, the per-endpoint latency histogram doubles as free solver-timing telemetry. Plus opt-in JSON log formatting (`configure_logging`, env `LOG_JSON`/`LOG_LEVEL`) and an optional structured access log (`LOG_ACCESS`). Env-gated (`METRICS_ENABLED`); added outermost (after rate limiting) so it measures even 429s. `tests/test_observability.py` (8 tests). **(M)**
- [x] **W4.3 — Optimizer golden/regression tests.** ✅ DONE & tested. `tests/test_optimizer_golden.py` (8 tests) locks the optimiser's behavioural contract so the W1.1 unification can't silently change results: byte-stable assignment on the deterministic heuristic path; capacity invariants on BOTH solver paths (OR-Tools + heuristic, parametrised); delivery conservation with per-STOP uniqueness (splits may ride different trucks); TND cost decomposition always sums to its total; objective label threaded through; and each objective still yields a valid, conserved plan. **Findings surfaced while writing these:** the `green`/`fast` objective modes do NOT produce a monotonic km or finish-time ordering on the real workbook (green can drive *more* km and even drop a marginal stop) — so the tests assert only the robust, true contracts, and the objective-mode trade-off is flagged for a W2.1 follow-up. **(M)**
- [x] **W4.4 — Rate limiting.** ✅ DONE & tested. Dependency-free per-IP fixed-window limiter (`app/rate_limit.py`) installed as middleware; tighter budget for solver/LLM endpoints (`/pareto`,`/stress-test`,`/confidence`,`/replan`,`/generate`,`/dashboard`,`/copilot/chat`). Env-gated (`RATE_LIMIT_ENABLED/DEFAULT/HEAVY/WINDOW`), disabled in tests. `tests/test_rate_limit.py` (3 tests).
- [ ] **W4.5 — TypeScript strict mode** (only after fixing every surfaced error). **(M)**
- [x] **W4.6 — File-upload validation.** ✅ DONE & tested. `/api/ingestion/upload` now enforces extension + declared content-type, a configurable size cap (`MAX_UPLOAD_MB`, default 25) via chunked streaming, and ZIP/xlsx magic-byte verification (rejects a renamed .exe/.csv); cleans up partial files. `tests/test_upload_validation.py` (4 tests).
- [x] **W4.7 — Login rate-limit / lockout.** ✅ DONE & tested. `LoginThrottle` (in `app/rate_limit.py`) locks an (ip, username) pair after `LOGIN_MAX_FAILS` (default 5) consecutive failures within `LOGIN_WINDOW` (default 15 min) → 429 + Retry-After; a successful login clears it. Env-gated (`LOGIN_LOCKOUT_ENABLED`), disabled in tests. `tests/test_login_lockout.py` (2 tests).

---

## Status snapshot (2026-06-14)
**Done & green:** Wave 0 (trust) + Wave 1 (W1.2 one KPI source · W1.3 Excel cache ·
W1.4 volume dimension) + Wave 2 W2.1–W2.5 (five flagship features) + W3.3 (board report)
+ Wave 4 W4.1/W4.4/W4.6/W4.7 (indexes, rate limiting, upload validation, login lockout).
Backend suite green (pytest exit 0); frontend production build passes. Six features live
on `frontend/app/generated-daily-planning/page.jsx`.
**Next up:** W1.1 unify optimizer (de-risk with W4.3 golden tests first) · W3.1 agentic
copilot wiring · W3.2 live control-tower map · W4.2 structured logging + `/metrics`.

## Progress Log
- _2026-06-14_ — Unified plan created from the two source roadmaps; false findings rejected; Wave 0 started.
- _2026-06-14_ — **Wave 0 complete & green.** Hardcoded path removed; copilot docs/memory corrected to Groq/Llama; least-privilege default role; bare-except fixed; DEMO DATA banner + `/api/data/source-status`; diag script relocated; pre-existing capacity/working-hours test realigned to the depart-cutoff contract. Full backend suite passes (pytest exit 0).
- _2026-06-14_ — **W2.1 Carbon & ESG flagship complete & green.** CO₂ accounting + objective modes + sustainability block in the plan builder; `/pareto` + `/esg-report` endpoints; `SustainabilityPanel` UI; 8 new tests. Frontend production build passes.
- _2026-06-14_ — **W2.2 Stress-Test Scenario Lab complete & green.** `demand_multiplier` knob; `/stress-test` endpoint (baseline + scenario deltas); `StressTestPanel` UI; 4 new tests. Frontend build passes.
- _2026-06-14_ — **W2.3 Monte-Carlo Plan Confidence complete & green.** `simulation_service.simulate_plan` (seeded); `/confidence` endpoint; `ConfidencePanel` UI (OTIF gauge, finish spread, fragile stops); 6 new tests. Frontend build passes. Three flagship "wow" features now live on the generated-daily-planning screen.
- _2026-06-14_ — **W2.4 Self-Healing Replan complete & green.** `DailyPlanBuilder.replan()`; `/replan` endpoint with old-vs-new diff; `DisruptionPanel` UI (break truck → diff → apply); 5 new tests. FOUR flagship wow features now live. Verified: breaking the busiest truck re-solves 14 residual stops, reassigns 5, flags those that can't be served, all in one call.
- _2026-06-14_ — **W2.5 Explainable Routing complete & green.** `/explain` endpoint (per-trip utilisation + binding constraint + counterfactual + per-stop reasoning); `ExplainPanel` UI; 3 new tests. FIVE wow features now on the generated-daily-planning screen. Verified: "fullest trip 100% pallets, binding=positions, 6 stops only this truck can serve, no smaller vehicle fits."
- _2026-06-14_ — **W3.3 Board report complete (frontend, build green).** `executiveReport.js` opens a print-ready Operations & Sustainability one-pager; "Board report (PDF)" button in SustainabilityPanel. SIX features live. Session total: Wave 0 + 6 features, 89 backend tests green, 7 frontend prod builds green.
- _2026-06-14_ — **W1.2 One KPI source complete & green.** `/api/metrics/kpi` falls back to live plan-derived KPIs (+CO₂ card) when ERD snapshots are empty; fixed a path bug (`parents[3]`); cached; `source` field. 2 new tests (91 total).
- _2026-06-14_ — **Committed ee23fef** (35 files): Wave 0 + 6 features + W1.2/W1.3.
- _2026-06-14_ — **W4.4 rate limiting + W4.6 upload validation complete & green** (committed 7cbe97a). +7 tests → 101.
- _2026-06-14_ — **W4.7 login lockout complete & green.** +2 tests → 103. Session: Wave 0 + 6 features + W1.2/W1.3 + W4.4/W4.6/W4.7, all green, on parallel-main.
- _2026-06-14_ — **W4.1 DB indexes complete & green** (committed d6ab6e3). `index=True` on hot FK/filter columns + `tests/test_db_indexes.py` (10 parametrised). Full backend suite green.
- _2026-06-14_ — **W1.4 Volume / m³ dimension complete & green.** Third capacity dimension wired through the global VRPTW, feasibility, hard-cap prefilter, schedulers, splits and reporting; frontend `TruckLane` shows m³; `tests/test_volume_dimension.py` (14 tests). Inert on current position-only data, correct the moment reel volumes arrive. Frontend prod build green. (committed 9dde437)
- _2026-06-14_ — **W3.2 Live Control Tower complete & green.** `control_tower.py::live_snapshot` interpolates each truck's live position along its route + predicted-late/geofence alerts (deterministic, no GPS); `/control-tower` endpoint; `ControlTowerPanel` + `ControlTowerMap` (clock scrubber, fleet roll-up, delay injection, alerts) on generated-daily-planning. `tests/test_control_tower.py` (14 tests). Full backend suite + frontend prod build green. SEVEN features now live on the planning screen.
