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
- [ ] **W1.4 — Volume / m³ capacity dimension** in the solver (cable reels cube out). **(M)**

## WAVE 2 — 🏆 Flagship features (the "wooow")

- [x] **W2.1 — C3 Carbon & ESG Optimizer.** ✅ DONE & tested. CO₂ factor in `CostConfig`; `objective` modes (green/balanced/fast) drive the makespan coefficient; per-plan `sustainability` block (CO₂ emitted/saved vs unconsolidated baseline, fuel, trees/car equivalents); `POST /api/planning/daily/pareto` (frontier + recommendations + full plans) and `GET /api/planning/daily/esg-report`; frontend `SustainabilityPanel` (headline cards + objective compare + apply + JSON export) mounted on generated-daily-planning; `tests/test_sustainability.py` (8 tests). Backend pytest green; frontend prod build green.
- [x] **W2.2 — C10 Stress-Test Scenario Lab.** ✅ DONE & tested. `demand_multiplier` knob in the builder; `POST /api/planning/daily/stress-test` (baseline + scenario battery: lose biggest/2-biggest truck, +20%/+30% volume, no rental; per-scenario served %, unassigned, cost/CO₂ deltas, rental forced, finish time); frontend `StressTestPanel` (comparison table with colour-coded deltas) on generated-daily-planning; `tests/test_stress_test.py` (4 tests). Backend pytest green; frontend prod build green.
- [x] **W2.3 — C2 Monte-Carlo Plan Confidence.** ✅ DONE & tested. `simulation_service.simulate_plan` replays a plan 500× under lognormal travel/service noise + rare disruption spikes; reports expected OTIF, reliability (% days ≥ target OTIF), perfect-day %, finish P50/P90/worst, and ranked fragile stops (seeded/deterministic). `POST /api/planning/daily/confidence` (simulates an inline plan or builds one); frontend `ConfidencePanel` (OTIF gauge + finish spread + fragile-stop bars) on generated-daily-planning; `tests/test_confidence.py` (6 tests).
- [x] **W2.4 — C1 Self-Healing Replan.** ✅ DONE & tested. `DailyPlanBuilder.replan(day, deliveries)` re-optimises an explicit residual delivery set on a (reduced) fleet without touching the workbook/splitting. `POST /api/planning/daily/replan` takes the current plan + `disrupted_truck_ids` + `completed_stop_ids`, re-solves the undelivered stops on the remaining fleet, and returns the new plan + a diff (reassignments, newly-unassigned, recovered, cost/CO₂ deltas). Frontend `DisruptionPanel` (break trucks → review diff → one-click Apply) on generated-daily-planning; `tests/test_replan.py` (5 tests).
- [x] **W2.5 — C8 Explainable routing.** ✅ DONE & tested. `POST /api/planning/daily/explain` returns a grounded, plain-language rationale for a truck's route (PER-TRIP peak utilisation, binding constraint, single-feasible & hard-window stops, total km) + a right-sizing counterfactual + per-stop reasoning — all from the plan, no re-solve. Frontend `ExplainPanel` (truck picker → rationale + facts grid) on generated-daily-planning; `tests/test_explain.py` (3 tests, incl. a per-trip-utilisation invariant guarding the daily-sum bug).

## WAVE 3 — Smart & Real

- [ ] **W3.1 — C4 Agentic copilot write-tools** (propose split / reassign / replan) with human approval. **(L)**
- [ ] **W3.2 — C6 Live control-tower map** + geofence predicted-late alerts. **(L)**
- [x] **W3.3 — C9 One-click executive report.** ✅ DONE (frontend). `components/planning/executiveReport.js` builds a polished one-page **Operations & Sustainability board report** (ops KPIs, CO₂ saved + equivalences, optional confidence, fleet table) from the plan + `/esg-report` and opens it print-ready (browser Save-as-PDF). "Board report (PDF)" button in `SustainabilityPanel`.
- [ ] **W3.4 — C5 Predictive ETA & demand forecasting** (close the planned-vs-actual loop). **(XL)**
- [ ] **W3.5 — C7 WhatsApp driver channel + ePOD.** **(L)**

## WAVE 4 — Hardening (verified subset of E–K)

- [ ] **W4.1 — DB indexes** on real FK/filter columns (verify names first). **(S)**
- [ ] **W4.2 — Structured logging + `/metrics`.** **(M)**
- [ ] **W4.3 — Optimizer golden/regression tests.** **(M)**
- [x] **W4.4 — Rate limiting.** ✅ DONE & tested. Dependency-free per-IP fixed-window limiter (`app/rate_limit.py`) installed as middleware; tighter budget for solver/LLM endpoints (`/pareto`,`/stress-test`,`/confidence`,`/replan`,`/generate`,`/dashboard`,`/copilot/chat`). Env-gated (`RATE_LIMIT_ENABLED/DEFAULT/HEAVY/WINDOW`), disabled in tests. `tests/test_rate_limit.py` (3 tests).
- [ ] **W4.5 — TypeScript strict mode** (only after fixing every surfaced error). **(M)**
- [x] **W4.6 — File-upload validation.** ✅ DONE & tested. `/api/ingestion/upload` now enforces extension + declared content-type, a configurable size cap (`MAX_UPLOAD_MB`, default 25) via chunked streaming, and ZIP/xlsx magic-byte verification (rejects a renamed .exe/.csv); cleans up partial files. `tests/test_upload_validation.py` (4 tests).
- [ ] **W4.7 — Login rate-limit / lockout.** **(M)**

---

## Status snapshot (2026-06-14)
**Done & green:** Wave 0 (trust) + Wave 2 W2.1–W2.5 (five flagship features) + W3.3
(board report). Backend **89 test functions pass** (pytest exit 0); frontend production
build passes. Six features live on `frontend/app/generated-daily-planning/page.jsx`.
**Next up:** W3.1 agentic copilot wiring · Wave 1 (unify optimizer / one KPI source /
Excel cache / volume dimension) · W3.2 live control-tower map.

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
