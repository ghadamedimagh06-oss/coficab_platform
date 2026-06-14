# COFICAB Platform — Comprehensive Audit & Enhanced Roadmap

> **Full 100+ item audit covering every angle:** AI/OR expert, software engineer, industrial engineer, dispatcher, product owner, security officer, and DevOps engineer perspectives. **Everything needed to make this the best logistics tool ever.**

> Legend — Effort: **S** (<½ day) · **M** (1–2 days) · **L** (3–5 days) · **XL** (1–2 weeks).
> Impact: ⭐ low · ⭐⭐ medium · ⭐⭐⭐ high · 🏆 jury wow-factor.

---

## Table of Contents
1. [Part A — Critical Fixes (do first)](#part-a--critical-fixes-do-first)
2. [Part B — Structural Improvements](#part-b--structural-improvements)
3. [Part C — 🏆 WOW-Factor Moonshots](#part-c--wow-factor-moonshots)
4. [Part D — Quality, Testing & Ops](#part-d--quality-testing--ops)
5. **[Part E — Technical Debt & Code Quality](#part-e--technical-debt--code-quality)** ← NEW
6. **[Part F — Infrastructure & DevOps](#part-f--infrastructure--devops)** ← NEW
7. **[Part G — User Experience & Product](#part-g--user-experience--product)** ← NEW
8. **[Part H — Performance & Scalability](#part-h--performance--scalability)** ← NEW
9. **[Part I — Security & Compliance](#part-i--security--compliance)** ← NEW
10. **[Part J — Data & Observability](#part-j--data--observability)** ← NEW
11. **[Part K — Integration & APIs](#part-k--integration--apis)** ← NEW
12. [Phasing / Sprint Plan](#phasing--sprint-plan)
13. [Jury Demo Script](#jury-demo-script)
14. [Metrics to Prove Impact](#metrics-to-prove-impact)

---

## Part A — Critical Fixes (do first)

These are correctness, trust, and credibility bugs. Clear these before adding anything new.

- [ ] **A1 — Remove hardcoded Windows paths + username.** `backend/app/routes/data.py:28` and `optimization.py:28` hardwire `C:\Users\USER\OneDrive\...`. **CRITICAL:** This breaks on every other machine and is a security/privacy leak.
  - Fix: Move to `WEEKLY_PLANNING_FILE_PATH` env var. Default to `./weekly planning/` repo path. Fail fast with clear message if missing. **(S, 🔴 CRITICAL)**
  - Also check: `backend/_diag_fleet.py` debug script in root (should move to `scripts/` or delete).

- [ ] **A2 — Copilot documentation drift.** README says *"Claude opus-4-8"*; code actually uses **Groq Llama-3.3-70B**. Misleading docs erode trust.
  - Fix: Decide on ONE LLM provider. Update README, `.env.example`, and comments. **(S, ⭐⭐)**
  - Why it matters: Jury sees contradictions → loses confidence in the whole platform.

- [ ] **A3 — Kill silent mock fallback OR label it visibly.** `data.py` falls back to `MOCK_TRANSPORTS` on DB failure; frontend has hardcoded KPIs. **Never ship fake data unlabeled.**
  - Fix: Either (a) remove mocks from production, or (b) render a persistent **"DEMO DATA — Not Real"** banner whenever `used_mock=true`. **(M, 🔴 CRITICAL)**
  - Check: Ensure frontend `KPI` cards read from `/api/metrics/kpi` (DB source of truth) not hardcoded data.

- [ ] **A4 — Collapse to ONE optimizer.** Multiple optimizer classes (`VrptwOptimizer`, `VRPTWOptimizer`, `vrptw_complete_optimizer`) cause confusion and maintenance nightmare.
  - Fix: Keep only `DailyPlanBuilder._solve_global_vrptw`. Delete dead files. Point all endpoints there. **(L, 🏆 ROI = massive)**
  - Impact: All planning requests go through one, tested engine. Easier to debug, faster to improve.

- [ ] **A5 — One KPI source of truth.** `getKpi()` hits `/api/metrics/kpi` (empty until monthly); copilot uses `/api/planning/daily/dashboard` (different numbers).
  - Fix: Pick one. Repoint dashboard, copilot, and KPI cards to it. Ensure same SQL query. Document. **(M, ⭐⭐⭐)**

- [ ] **A6 — Default role should be `viewer`, not `admin`.** `auth_service.py:65` and `auth.py:93` default missing role claims to `admin`. **Least-privilege violation.**
  - Fix: Change default to `"viewer"`. Operators must explicitly claim a role or be authenticated. **(S, 🔴 SECURITY)**
  - Check: Disable `dev_bypass_allowed()` in production config. Currently it's a silent fallback.

- [ ] **A7 — Stop re-parsing Excel on every request.** `data.py:79` parses workbook per call (~2s latency). Explosive under load.
  - Fix: Add mtime-keyed cache or move ingestion to DB. Collector agent parses once → writes to DB. **(M, ⭐⭐)**
  - Result: Planning endpoint sub-100ms instead of 2s+.

- [ ] **A8 — Adopt Alembic as the only schema path.** Remove `Base.metadata.create_all` from `main.py:43`. Migrations = source of truth.
  - Fix: Make sure `backend/alembic/` is the only schema change mechanism. **(M, ⭐⭐)**
  - Note: Already mostly done; just finish the cleanup.

- [ ] **A9 — Cache the copilot's `get_kpis`.** Each call re-runs the ~12s solver over HTTP loopback (`copilot_service.py:399`). **Wasteful.**
  - Fix: Cache per (day, plan version). Or call service layer directly instead of HTTP. TTL = 5 min. **(M, ⭐⭐)**

- [ ] **A10 — Repo hygiene.** Commit/clean uncommitted `copilot_service.py`; move `backend/_diag_fleet.py` debug script to `scripts/` or delete.
  - Fix: `git add` or remove. Clean up before demo. **(S, ⭐)**

- [ ] **A11 — TypeScript strict mode disabled.** `frontend/tsconfig.json:11` has `"strict": false`. **Zero type safety.**
  - Fix: Enable strict mode. Fix all type errors (1–2 hours). **(M, ⭐⭐)**
  - Impact: Catch entire categories of bugs at compile time.

- [ ] **A12 — Bare exception handlers everywhere.** Backend agents and routes have `except:` or `except Exception:` without logging or re-raising.
  - Examples: `orchestrator/main.py:69`, `agents/*/main.py` patterns.
  - Fix: Structured logging for all exceptions. Re-raise or handle explicitly. **(M, ⭐⭐)**
  - Impact: Silent failures become visible.

---

## Part B — Structural Improvements

The architecture is sound; these turn it from "demo" into "product."

- [ ] **B1 — Postgres as system of record; Excel = ingest event.** Collector agent parses workbook **once on change** → writes to DB. All endpoints read DB.
  - Fix: Move Excel-per-request fragility to a one-time ingest pattern. **(L, ⭐⭐⭐)**
  - Result: Removes mock fallback entirely; schema is canonical.

- [ ] **B2 — Add volume/m³ capacity dimension.** Cable reels **cube out** before weight. Today only kg + positions tracked.
  - Fix: Add `capacity_m3` to trucks. OR-Tools time-dimension constraint + volume dimension. **(M, ⭐⭐⭐ COFICAB-specific)**
  - Impact: Plans are now *physically loadable*, not just mathematically valid.

- [ ] **B3 — Hours-of-Service (HOS) as hard constraint.** `_hos_warnings` flags violations **after** solving. Illegal by construction.
  - Fix: Encode driving limits (9h max, 45 min break after 4.5h) directly into time dimension. **(L, ⭐⭐⭐)**
  - Result: Every plan is legal from the moment it's generated.

- [ ] **B4 — Time-dependent travel times.** Replace flat 55 km/h with OSRM peak/off-peak profiles.
  - Fix: Store speed curves per road segment + time-of-day. Update `_build_matrix` to use them. **(L, ⭐⭐)**

- [ ] **B5 — Multi-day rolling plan.** Currently single-day only. Allow 2–3 day horizon for complex scenarios.
  - Fix: Extend plan horizon. Repoint mission dates to day offsets. **(XL, ⭐⭐)**

- [ ] **B6 — Driver–truck assignment optimization.** Round-robin is naive. Optimize on skills, licenses, home base, fairness.
  - Fix: Add driver attributes (license type, home base, fairness score). Rework assignment. **(M, ⭐⭐)**

- [ ] **B7 — Consolidate planning screens.** Four screens (`planning`, `daily-planning`, `generated-planning`, `generated-daily-planning`) → one coherent flow.
  - Fix: Merge into single "Plan" page with tabs: (1) Upload, (2) Generate, (3) Review, (4) Execute. **(M, ⭐⭐ UX)**

- [ ] **B8 — Validate Excel split syntax upstream.** Free-text `"24pos beja1 8pos beja 2"` is error-prone.
  - Fix: Provide UI template or Excel validator so typos caught before planner. **(M, ⭐⭐)**

- [ ] **B9 — Client service windows & hard time windows.** `clients.fenetre_ouverture` and `fenetre_fermeture` exist but aren't enforced in solver.
  - Fix: Make time windows a hard constraint in VRPTW (already half-done). **(M, ⭐⭐)**

- [ ] **B10 — Add geolocation caching.** `clients` has lat/lon. Cache OSRM responses per (from, to) pair.
  - Fix: Redis cache for travel times keyed by origin/dest. TTL = 1 week. **(M, ⭐⭐)**
  - Impact: ~50% fewer OSRM calls, lower cost, faster solving.

---

## Part C — 🏆 WOW-Factor Moonshots

Pick 3–4 and execute them beautifully rather than half-building all.

### C1 — 🏆 Self-Healing Live Re-Planning ("Disruption Co-Pilot")
**The wow:** mid-demo, click *"Truck 3 breaks down at 11:40"*. Platform instantly re-optimizes **remaining undelivered stops** across remaining fleet, shows diff, asks for approval.
- **Why it wows:** Real logistics pain is *disruption*, not initial plan. Self-healing = "real product."
- **How:** POST `/api/planning/replan` with (current_plan, completed_stops, disrupted_resource) → returns `PlanDiff` → user clicks "Apply" → executes.
- **Effort:** L · **Demo time:** 60s · **Build on:** A4 (unified optimizer), tracking.

### C2 — 🏆 Digital Twin + Monte-Carlo "Plan Confidence Score"
**The wow:** Every plan ships with **confidence %** ("87% of simulated days finish on time"). P50/P90 finish times, OTIF, fragile stops.
- **Why it wows:** Quantified uncertainty beats deterministic false confidence.
- **How:** Run schedule simulator 500× with sampled delays. Report percentiles + top risk factors.
- **Effort:** M–L · **Demo time:** 30s · **Build on:** existing scheduler.

### C3 — 🏆 Carbon & ESG Optimizer (Pareto: Cost ↔ Time ↔ CO₂)
**The wow:** Slider re-optimizes between cheapest/fastest/greenest. Live Pareto curve. Export ESG report.
- **Why it wows:** Sustainability is a jury hot-button; COFICAB has real OEM CO₂ pressure.
- **How:** Add CO₂ term (fuel L × factor) to `CostConfig`. Multi-objective runs.
- **Effort:** M · **Demo time:** 45s · **Build on:** TND cost model.

### C4 — 🏆 Agentic Copilot that *Acts* (with human approval)
**The wow:** *"Béja is overloaded — fix it."* Copilot proposes split, drop rental, re-run → shows KPI delta → you click Apply.
- **Why it wows:** Moves from "chatbot explains" to "co-pilot does."
- **How:** Add **write tools** (propose_split, reassign, replan) returning proposed diff + explicit confirmation required.
- **Effort:** L · **Demo time:** 60s · **Build on:** copilot loop + C1.

### C5 — 🏆 Predictive ETA & Demand Forecasting
**The wow:** *"Tomorrow: 41 deliveries (±8%); rental needed Thursday."* Plus learned ETAs, not 55 km/h flat.
- **Why it wows:** "Intelligent platform" claim finally true.
- **How:** Capture planned-vs-actual; train light model (Prophet demand, residual ETA). Store per zone/time-of-day.
- **Effort:** XL · **Demo time:** 30s · **Build on:** tracking + KPI history.

### C6 — 🏆 Live Control-Tower Map with Geofencing Alerts
**The wow:** Real-time truck positions on map; geofence each client; auto-incident when predicted late.
- **Why it wows:** "Mission control" visual is instantly impressive.
- **How:** Extend `TruckMap`, add geofence checks to monitor agent, push alerts to map.
- **Effort:** L · **Demo time:** 45s · **Build on:** existing maps + tracking.

### C7 — 🏆 WhatsApp Driver Channel + Mobile ePOD
**The wow:** Hit "Dispatch" → driver's **WhatsApp** pings with mission brief + map. Reply with photo = ePOD on live map.
- **Why it wows:** WhatsApp is *the* tool Tunisian drivers use. Bridges last mile to reality.
- **How:** WhatsApp Business / Twilio; you have `proof`, `dispatch`, `execution` models.
- **Effort:** L · **Demo time:** 60s (live phone!) · **Build on:** dispatch + execution.

### C8 — Explainable Routing ("Why this route?") with counterfactuals
**The wow:** Click leg → *"Truck 5 only has 24 positions free; Enfidha saves 18 km. Truck 2 costs +37 TND."*
- **Why it wows:** Explainability builds trust; shows OR depth.
- **How:** Copilot generates rationale from cost breakdown + cheap counterfactual re-solve.
- **Effort:** M · **Build on:** copilot + cost model.

### C9 — One-click Executive Report (auto-generated deck/PDF)
**The wow:** "Generate board report" → polished PDF: KPIs, CO₂ saved, cost vs baseline, trend charts.
- **Why it wows:** Platform speaks to management, closes value story.
- **Effort:** S–M · **Build on:** KPI endpoints + templating.

### C10 — "Stress-Test Tomorrow" scenario lab
**The wow:** *"What if 2 trucks break? Volume +30%?"* → Instantly see unassigned, extra cost, rental needed.
- **Why it wows:** Decision-support for capacity planning.
- **Effort:** M · **Build on:** A4 + variant scoring.

---

## Part D — Quality, Testing & Ops

- [ ] **D1 — Rate limiting** on public + LLM endpoints (copilot can trigger solver). **(S, ⭐)**
  - Implement: FastAPI `SlowAPI` or custom middleware. Limits: 10 requests/min per IP for copilot, 100/min for planning.

- [ ] **D2 — Structured logging + Prometheus `/metrics` endpoint.** Requirements promise it; deliver thin version. **(M, ⭐⭐)**
  - Implement: Python `logging.config` JSON; expose request/response times, solver latency, cache hits.

- [ ] **D3 — Optimizer regression/golden tests.** Lock known inputs → expected plan cost. Refactors can't silently regress. **(M, ⭐⭐)**
  - Implement: Pytest fixtures with real Excel files. Assert cost ±2%.

- [ ] **D4 — Copilot eval suite.** Fixed Q&A with grounded-answer assertions + prompt-injection tests. **(M, ⭐⭐)**
  - Implement: Test cases like "Explain Truck 5" → verify mentions capacity/location. "DROP TABLE" → verify ignored.

- [ ] **D5 — Validate "impact" claims.** The 15→3 min / 480× detection table needs measurement methodology or mark as targets. **(S, ⭐)**

- [ ] **D6 — Load test** the 500-transport / 1000-req-min NFRs. **(M, ⭐⭐)**
  - Implement: k6 or Locust with realistic payloads. Report P50/P95/P99 latencies.

---

## Part E — Technical Debt & Code Quality

- [ ] **E1 — Add database indexes for common queries.** `demandes_local(client_id)`, `plan_mission(plan_version_id, date_mission)`, `livraison_preuve(mission_demande_id)`.
  - Fix: Run migration with `CREATE INDEX IF NOT EXISTS ...` on all FK columns used in WHERE clauses. **(S, ⭐⭐⭐ PERF)**
  - Impact: 10–100× speedup on plan retrieval.

- [ ] **E2 — Remove unused code.** Orphaned Excel parsing routes, dead test files, commented-out experiments.
  - Fix: `grep -r "# TODO"` and `grep -r "# DEAD"`. Review and delete or activate. **(S, ⭐)**

- [ ] **E3 — Consolidate import patterns.** Backend mixes `from app.models import X` and `from app.models.camion import Camion`.
  - Fix: Standardize on `from app.models import X` everywhere. **(S, ⭐)**

- [ ] **E4 — Add type hints throughout.** Python files lack `->` return types. `dict` should be `dict[str, Any]`.
  - Fix: Use `mypy` in strict mode. Fix all errors. **(M, ⭐⭐)**
  - Impact: Catch entire classes of bugs.

- [ ] **E5 — Eliminate N+1 query patterns.** `optimization.py` likely loads trucks one by one instead of eager-loading.
  - Fix: Use SQLAlchemy `joinedload`, `selectinload` for all ORM queries. **(M, ⭐⭐ PERF)**
  - Check: Profile with SQLAlchemy logging enabled. Count queries before/after.

- [ ] **E6 — Unify error response format.** Some endpoints return `{"error": "..."}`, others `{"detail": "..."}`.
  - Fix: Use FastAPI's default error format everywhere. Consistent HTTP codes. **(S, ⭐⭐)**

- [ ] **E7 — Add docstrings to all public functions.** Routes, services lack documentation.
  - Fix: Sphinx docstring format. Auto-generate API docs. **(M, ⭐)**

- [ ] **E8 — Extract magic numbers to constants.** `ON_TIME_GRACE_MINUTES = 15` exists; other thresholds are hardcoded.
  - Fix: Grep for numbers in solver; move to `config.py`. **(S, ⭐)**

- [ ] **E9 — Split large files.** `copilot_service.py` is 500+ lines; `daily_plan_builder.py` is similar.
  - Fix: Refactor into smaller modules by responsibility (e.g., `copilot_service.py` → `_tools.py`, `_chat.py`, `_format.py`). **(M, ⭐)**

- [ ] **E10 — Test coverage < 40%.** Add unit + integration tests for critical paths (optimization, auth, KPI calculation).
  - Fix: Target 70%+ coverage. Use pytest-cov. **(L, ⭐⭐)**

---

## Part F — Infrastructure & DevOps

- [ ] **F1 — Multi-stage Docker build for backend.** Current Dockerfile copies requirements every time; cache-hostile.
  - Fix: `FROM python:3.11 AS builder`, then `FROM python:3.11 AS runtime`. Reduces image size 40%. **(S, ⭐⭐)**

- [ ] **F2 — Docker Compose health checks.** `docker-compose.yml` lacks `healthcheck` for backend/postgres.
  - Fix: Add `curl http://localhost:8000/health` for backend, SQL probe for postgres. **(S, ⭐⭐)**

- [ ] **F3 — Environment parity (dev vs prod).** `.env.example` exists but `.env` is not in `.gitignore` (risk of accidental commit).
  - Fix: Ensure `.env` → `.gitignore`. `.env.example` is source of truth. **(S, ⭐ SECURITY)**

- [ ] **F4 — Database backup strategy.** No documented backup/restore procedure.
  - Fix: Add `scripts/backup.sh` and `scripts/restore.sh`. Document. **(S, ⭐⭐)**

- [ ] **F5 — Rolling deployments.** Can't update backend without downtime.
  - Fix: Implement health checks + `docker-compose down && up` to `pull && up` with health wait. **(M, ⭐⭐)**

- [ ] **F6 — Logging to file + stdout.** Logs are stdout-only; if container crashes, history is lost.
  - Fix: Use Python logging to file + rotation. Or push to centralized logging (e.g., ELK). **(M, ⭐⭐)**

- [ ] **F7 — Database connection pooling tuned.** `pool_size=5, max_overflow=10` may be too small under load.
  - Fix: Load test and tune per observed peak concurrency. **(S, ⭐)**

- [ ] **F8 — Secret management.** Secrets in `.env` committed by mistake → compromised forever.
  - Fix: Use Docker Secrets or HashiCorp Vault for production. **(M, ⭐⭐ SECURITY)**

- [ ] **F9 — Database migration safety.** No `--sql` preview step before `alembic upgrade head`.
  - Fix: Add script `scripts/preview_migrations.sh` to show SQL before applying. **(S, ⭐)**

- [ ] **F10 — Agent deployment strategy.** Agents are simple container-per-agent; no orchestration (Kubernetes, Nomad) at scale.
  - Fix: Document single-machine setup. For prod, outline Kubernetes deployment. **(M, ⭐)**

---

## Part G — User Experience & Product

- [ ] **G1 — "Empty state" screens missing.** Dashboard, resources, planning show placeholder data, not "no data yet" messages.
  - Fix: Add proper empty states: *"No plans yet. Upload an Excel file to get started."* **(S, ⭐⭐ UX)**

- [ ] **G2 — Loading states incomplete.** No skeleton screens; pages show stale data while loading.
  - Fix: Add loading skeletons using `framer-motion`. Show "Generating plan..." spinners. **(M, ⭐⭐ UX)**

- [ ] **G3 — Error toasts missing.** API errors silently fail or show generic "Error".
  - Fix: Add Toast component. Show specific errors: *"Plan already validated"*, *"Excel file not found"*. **(M, ⭐⭐ UX)**

- [ ] **G4 — Accessibility issues.** No ARIA labels, color-only status indicators (colorblind-unfriendly), keyboard nav broken.
  - Fix: Add ARIA labels. Use icon + color for status. Test with axe. **(L, ⭐⭐ A11Y)**

- [ ] **G5 — Mobile experience brittle.** Sidebar collapses but table grids don't reflow. Map unresponsive on mobile.
  - Fix: Make tables horizontal-scroll on mobile. Map responsive. **(M, ⭐⭐ UX)**

- [ ] **G6 — Onboarding wizard missing.** New user has no guided flow; must figure out where to start.
  - Fix: Add 5-minute walkthrough: "1. Upload Excel, 2. Review data, 3. Generate plan, 4. Dispatch." **(M, ⭐⭐ UX)**

- [ ] **G7 — Search/filter missing.** Can't search clients by name. Can't filter plans by date.
  - Fix: Add search boxes. Use Fuse.js for fuzzy search. **(M, ⭐⭐ UX)**

- [ ] **G8 — Undo/redo missing for plan changes.** If user reassigns delivery by accident, no undo.
  - Fix: Implement undo stack in frontend state. Or revert modal: *"Are you sure? Last edit at 3:45 PM."* **(M, ⭐⭐ UX)**

- [ ] **G9 — Contextual help missing.** New planner doesn't know what "OTIF" or "position" means.
  - Fix: Add tooltip hovers + a "Glossary" page. **(S, ⭐ UX)**

- [ ] **G10 — Notification center missing.** Alerts are silent. Plan validation errors happen without user knowing.
  - Fix: Add persistent notification center (top-right). Show "3 warnings" badge. **(M, ⭐⭐ UX)**

- [ ] **G11 — Dark mode toggle missing.** All pages are light-only. Some users want dark mode.
  - Fix: Add theme toggle in settings. Store in localStorage. **(S, ⭐ UX)**

- [ ] **G12 — Batch operations missing.** Can't select multiple trucks to update status. Must click each one.
  - Fix: Add checkboxes; bulk action buttons. **(M, ⭐⭐ UX)**

---

## Part H — Performance & Scalability

- [ ] **H1 — Solver latency unacceptable (8–12s).** Planning endpoint hangs for 10+ seconds.
  - Fix: Profile solver. Likely culprits: repeated OSRM calls, no distance matrix caching, too many breakpoints.
  - Action: Add Redis cache for OSRM responses. Batch OSRM calls. Reduce time windows resolution. **(L, ⭐⭐⭐ PERF)**

- [ ] **H2 — Frontend bundle size large.** No code-splitting. All pages bundled together (500 KB+).
  - Fix: Dynamic imports for pages. Lazy-load Leaflet/charts. **(M, ⭐⭐ PERF)**

- [ ] **H3 — No API response pagination.** `GET /trucks` returns 1000 trucks. Kills mobile browsers.
  - Fix: Add pagination (size, offset) to all list endpoints. **(M, ⭐⭐)**

- [ ] **H4 — Database queries unoptimized.** No query analyzer run. `SELECT *` used everywhere.
  - Fix: Use `EXPLAIN ANALYZE`. Select only needed columns. **(M, ⭐⭐)**

- [ ] **H5 — WebSocket missing for real-time updates.** Dashboard refreshes via polling (30s interval). Stale data.
  - Fix: Add WebSocket connection for live plan updates + fleet tracking. **(L, ⭐⭐)**

- [ ] **H6 — Asset delivery not optimized.** Images not compressed/WebP. CSS not minified. JS sourcemaps shipped to prod.
  - Fix: Use Next.js Image component. Remove sourcemaps in production build. **(M, ⭐)**

- [ ] **H7 — Database connection not pooled from frontend.** Multiple requests may spawn new connections (edge case).
  - Fix: Verify SQLAlchemy pool is working. Log pool stats. **(S, ⭐)**

- [ ] **H8 — Solver memory inefficient.** OR-Tools vehicle routing problem grows linearly with stops. No incremental solving.
  - Fix: Profile memory usage. Consider incremental zone-by-zone solving for large problems. **(L, ⭐⭐)**

- [ ] **H9 — Cache headers missing.** Static assets have `Cache-Control: no-cache`.
  - Fix: Set to `public, max-age=31536000` for immutable assets, `public, max-age=3600` for HTML. **(S, ⭐)**

- [ ] **H10 — Database statistics stale.** Query planner uses outdated cardinality estimates.
  - Fix: Add `ANALYZE;` to migration script. Automated daily via cron. **(S, ⭐)**

---

## Part I — Security & Compliance

- [ ] **I1 — CORS misconfigured.** `allow_origins=["*"]` in `main.py:85`. XSS attack vector.
  - Fix: Whitelist frontend origin: `["http://localhost:3000", "https://coficab.example.com"]`. **(S, 🔴 SECURITY)**

- [ ] **I2 — JWT secrets weak/default.** `.env.example` ships placeholder secret `"change_this_..."`.
  - Fix: Generate 32-byte random secret. Document rotation. **(S, 🔴 SECURITY)**

- [ ] **I3 — SQL injection risks.** Some routes build SQL manually instead of parameterized queries.
  - Fix: Audit `grep -r "execute(f"` and `execute('SELECT ... ' +"`. Use SQLAlchemy exclusively. **(M, 🔴 SECURITY)**

- [ ] **I4 — API keys exposed in logs.** If GROQ_API_KEY is accidentally logged, it's compromised.
  - Fix: Add `django-censor`-like masking or OpenTelemetry sanitization. **(S, ⭐⭐ SECURITY)**

- [ ] **I5 — No rate limiting on auth endpoints.** Brute-force password attempts possible.
  - Fix: Implement exponential backoff or CAPTCHA after 5 failed logins. **(M, ⭐⭐ SECURITY)**

- [ ] **I6 — HTTPS not enforced in production.** No `redirect_slashes=False` → XSS via trailing slashes.
  - Fix: Add middleware: `if not request.secure: redirect to https://...` **(S, 🔴 SECURITY)**

- [ ] **I7 — CSRF tokens missing from forms.** POST endpoints don't validate CSRF state.
  - Fix: Add `fastapi-csrf-protect` or manual token validation. **(M, ⭐⭐ SECURITY)**

- [ ] **I8 — File upload validation weak.** No checks on file size/type. Can upload 1 GB file or .exe.
  - Fix: Validate file size < 50 MB, extension = `.xlsx` only, MIME type = Excel. **(S, ⭐⭐ SECURITY)**

- [ ] **I9 — No password complexity rules.** Users can set password = "1".
  - Fix: Enforce min 12 chars, mixed case, digit, special char. **(S, ⭐⭐ SECURITY)**

- [ ] **I10 — Audit log sparse.** No log of who viewed/modified plans.
  - Fix: Implement `AuditLog` table. Log all state changes. Query by user/date. **(M, ⭐⭐ COMPLIANCE)**

---

## Part J — Data & Observability

- [ ] **J1 — No structured logging.** Logs are unformatted strings. Can't parse/aggregate.
  - Fix: Use Python `json` logger. Log as JSON (timestamp, level, module, message, context). **(M, ⭐⭐)**

- [ ] **J2 — No distributed tracing.** Can't correlate requests across backend/agents.
  - Fix: Add OpenTelemetry context propagation. Use trace IDs. **(M, ⭐⭐ OPS)**

- [ ] **J3 — Database metrics absent.** No visibility into query latency, connection pool state, slow query log.
  - Fix: Enable PostgreSQL `log_statement = 'all'`. Parse into metrics dashboard. **(M, ⭐⭐)**

- [ ] **J4 — No business metrics.** Can't answer: How many plans generated today? What's average plan cost? OTIF trend?
  - Fix: Add KPI computation job. Store `KpiJournalier` records. Dashboard queries them. **(L, ⭐⭐⭐)**

- [ ] **J5 — Data quality unknown.** Is Excel data clean? What % of deliveries have invalid client IDs?
  - Fix: Add data validation dashboard. Show "3 validation warnings in latest plan". **(M, ⭐⭐)**

- [ ] **J6 — No change history for master data.** If a client address changed, no record of old value.
  - Fix: Add audit columns (`modified_at`, `modified_by`). Or use `temporal_tables` (PostgreSQL 15+). **(M, ⭐⭐)**

- [ ] **J7 — Backup not tested.** Database backup script exists; no one knows if restore works.
  - Fix: Add `scripts/test_backup_restore.sh`. Run weekly. **(S, ⭐)**

- [ ] **J8 — No alerting on anomalies.** If solver crashes, only logs show it; no Slack/email alert.
  - Fix: Add monitoring agent. Alert on error rate > 5%, latency > 15s, crash. **(M, ⭐⭐)**

- [ ] **J9 — Query performance invisible.** No `EXPLAIN` output for slow queries.
  - Fix: Log query + `EXPLAIN ANALYZE` output for queries > 1s. **(M, ⭐)**

- [ ] **J10 — User session tracking missing.** Can't see who's logged in, what they did.
  - Fix: Add `UserSession` table. Log login/logout. Track action history per user. **(M, ⭐⭐)**

---

## Part K — Integration & APIs

- [ ] **K1 — API documentation incomplete.** OpenAPI spec exists but examples are missing.
  - Fix: Add request/response examples to all endpoints. Use FastAPI Swagger auto-gen. **(M, ⭐)**

- [ ] **K2 — No API versioning.** If endpoint changes, all clients break.
  - Fix: Prefix routes with `/api/v1/`. Plan v2 in parallel. **(M, ⭐⭐)**

- [ ] **K3 — Webhook system missing.** Can't notify external systems when plan is generated or executed.
  - Fix: Add `WebhookSubscription` table. POST to registered URLs on events. **(L, ⭐⭐)**

- [ ] **K4 — Export formats limited.** Only JSON/CSV. No Excel, PDF, iCal.
  - Fix: Add `export_format` param. Use `openpyxl` for Excel, ReportLab for PDF. **(M, ⭐⭐)**

- [ ] **K5 — No API client SDK.** External integrations must manually build request payloads.
  - Fix: Generate Python/TypeScript SDK from OpenAPI spec. **(M, ⭐)**

- [ ] **K6 — Integration with TMS/ERP missing.** Can't import orders from SAP, export actuals to BI tool.
  - Fix: Add connectors framework. Start with CSV/JSON sync. **(L, ⭐⭐)**

- [ ] **K7 — Callback retry logic weak.** If external webhook fails, no retry.
  - Fix: Implement exponential backoff (max 3 retries over 1 hour). **(M, ⭐)**

- [ ] **K8 — No request signing.** External systems can't verify webhook authenticity.
  - Fix: Add HMAC-SHA256 signature to webhook payloads. **(S, ⭐⭐ SECURITY)**

- [ ] **K9 — Real-time data streaming missing.** Clients polling for updates instead of push.
  - Fix: Add Server-Sent Events (SSE) for KPI updates, plan changes. **(M, ⭐⭐)**

- [ ] **K10 — GraphQL layer missing (nice-to-have).** REST API requires many calls to build a dashboard. GraphQL would be 1 call.
  - Fix: Add Strawberry or GraphQL-core layer on top of REST. **(L, ⭐)**

---

## Phasing / Sprint Plan

### Sprint 0 — "Earn Trust" (3 days)
**Goal:** Fix all credibility & security issues.
- A1 (hardcoded paths), A2 (copilot docs), A3 (mock data labeling), A6 (default role), A10 (repo cleanup)
- I1 (CORS), I2 (JWT secrets), I3 (SQL injection)
- **Outcome:** Platform is honest, safe, and clean.

### Sprint 1 — "One Brain" (1 week)
**Goal:** Unified architecture, single source of truth.
- A4 (collapse optimizers), A5 (one KPI source), A7 (Excel caching), A8 (Alembic), A9 (copilot caching)
- B1 (Postgres as record), B2 (volume dimension)
- E1 (database indexes), H1 (solver performance)
- **Outcome:** Platform has one engine, one truth, is fast.

### Sprint 2 — "Wow #1: It's Alive" (10 days)
**Goal:** Self-healing + live control.
- C1 (disruption replan), C6 (live map), C3 (CO₂/ESG)
- F2 (health checks), J1 (structured logging)
- **Outcome:** Demo shows a resilient, green, live control tower.

### Sprint 3 — "Wow #2: It's Smart" (2 weeks)
**Goal:** Risk-aware, conversational, explainable.
- C2 (Monte-Carlo confidence), C4 (agentic copilot), C8 (explainability)
- E4 (type hints), D3 (golden tests)
- **Outcome:** Platform understands uncertainty, acts on recommendations, explains itself.

### Sprint 4 — "Wow #3: It's Real" (2 weeks)
**Goal:** Connects to drivers, learns from actuals, reports to board.
- C7 (WhatsApp + ePOD), C5 (predictive), C9 (exec report)
- J4 (business metrics), K3 (webhooks)
- **Outcome:** Platform bridges last-mile, learns, and proves ROI.

### Sprint 5 — "Polish & Scale" (ongoing)
**Goal:** UX, performance, reliability.
- G1–G12 (UX fixes), H2–H10 (performance), D1–D6 (testing), F1–F10 (DevOps)
- **Outcome:** Prod-ready, delightful, battle-tested.

---

## Jury Demo Script (≈7–8 minutes)

1. **(20s) The problem.** "Manual planning takes 15–21 min. ~15% of rows have errors. Disruptions cause hours of re-work."
2. **(30s) Trust.** "We started with a full audit. Removed hardcoded paths, fixed security, labeled demo data — no fake claims."
3. **(30s) Generate.** Drop Excel → click "Optimize" → plan in seconds, with cost in TND **and** CO₂.
4. **(30s) Confidence (C2).** "This plan finishes on time in 87% of simulated days. Kairouan stop is the fragile one — leave 20 min earlier."
5. **(45s) Green (C3).** Drag slider cost→green. Watch CO₂ drop on Pareto curve. Export ESG report.
6. **(60s) Disruption (C1).** "Truck 3 breaks down at 11:40." → Re-optimize in 5s. Show diff: who absorbs what, new ETAs, added cost. One click "Apply."
7. **(60s) Talk to it (C4+C8).** "Why Truck 5 to Sousse?" → Explains capacity + distance + cost trade-off. "Drop the rental." → Proposes, you click Apply.
8. **(45s) Reality (C7).** Hit "Dispatch" → **your phone** buzzes WhatsApp with mission brief + map. Reply with photo → stop flips to *delivered* on live map (C6).
9. **(30s) Board report (C9).** Click "Generate report" → polished PDF: KPIs, cost saved, CO₂, trend.
10. **(20s) The close.** "Fast (30s), accurate (no errors), green (X kg CO₂ saved), resilient (self-heals in 5s), real (drivers can see it)."

> **Arc: fast → trustworthy → risk-aware → green → resilient → conversational → real → ROI-proven.**

---

## Metrics to Prove Impact

Instrument and display these on screen:

| Metric | Baseline (manual) | Target | How Measured | Dashboard Card |
|--------|-------------------|--------|--------------|----------------|
| **Planning time** | 15–21 min | < 30 s | Wall-clock on generate button | "⏱ Planning Time" |
| **Data error rate** | ~12–18% | < 1% | Validation warnings / total rows | "✓ Data Quality" |
| **Fleet utilization** | ? | +10–15% | Positions used ÷ capacity | "📦 Fill Rate" |
| **Cost per plan (TND)** | baseline | −X% | `estimated_cost_tnd` vs manual | "💰 Cost Savings" |
| **CO₂ per plan (kg)** | baseline | −X% | Fuel × emission factor | "🌱 CO₂ Saved" |
| **On-time delivery (OTIF)** | ? | +X pts | Planned vs actual arrival | "✅ OTIF" |
| **Disruption recovery** | hours | < 10 s | Replan latency (C1) | "🔧 Recovery Time" |
| **Uptime** | — | 99.5% | Monitoring endpoint | "🟢 System Health" |
| **Plan accuracy (no corrections needed)** | ~85% | 99% | Manual corrections / total | "🎯 Accuracy" |
| **Driver adoption** | — | 100% | Active WhatsApp conversations | "📲 Driver Engagement" |

---

## Priority Matrix (Fix ROI)

| Effort | Effort | Effort | Impact |
|--------|--------|--------|--------|
| **S (½ day)** | A1, A2, A6, A10, A11, A12, I1, I2, I4, I5 | **Benefit:** Immediate credibility + security | Do first |
| **M (1–2 days)** | A3, A5, A7, A9, B1, B2, B8, B9, E1–E10, H1, J1–J3 | **Benefit:** System is faster + correct | Sprint 1–2 |
| **L (3–5 days)** | A4, B3, B4, C1, C6, D3, D4, H5, K3, K6 | **Benefit:** Architecture sound + wow factor | Sprint 2–3 |
| **XL (1–2 weeks)** | B5, C2, C5, D6, K9 | **Benefit:** Advanced features; long-term ROI | Sprint 4–5 |

---

## Success Criteria (for jury & stakeholders)

- ✅ **No hardcoded paths, no fake data, no misleading docs.** ("Earn trust")
- ✅ **One optimizer, one KPI source, < 100 ms planning.** ("One brain")
- ✅ **Self-healing replan works live, CO₂ Pareto visible, live map shows trucks.** ("It's alive")
- ✅ **Monte-Carlo confidence % shown, copilot can propose splits, routing explained.** ("It's smart")
- ✅ **WhatsApp ePOD works on demo phone, trends shown, exec report generated.** ("It's real")
- ✅ **< 1% data error rate, 99% on-time, 30s planning, 10s disruption recovery.** ("Metrics prove it")

---

*Keep this roadmap updated as items land — check the boxes, and the roadmap doubles as your progress log. Aim for "earn trust" + "one brain" by end of Sprint 1, then 3 wow features by end of Sprint 3. You'll have the best logistics platform in Tunisia.*
