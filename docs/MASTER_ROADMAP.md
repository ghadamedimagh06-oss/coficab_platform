# COFICAB Platform — Master Roadmap & To-Do

> Multi-perspective audit (AI/OR expert · software engineer · industrial engineer · dispatcher · strict reviewer) **plus** a moonshot feature set designed to make a jury say *wooow*.
>
> Legend — Effort: **S** (<½ day) · **M** (1–2 days) · **L** (3–5 days) · **XL** (1–2 weeks).
> Impact: ⭐ low · ⭐⭐ medium · ⭐⭐⭐ high · 🏆 jury wow-factor.

> UPDATE — Expanded audit added: I performed a deeper full-codebase audit and produced a companion, expanded roadmap with 100+ actionable items (security, infra, UX, performance, observability, and additional moonshots). See [COMPREHENSIVE_AUDIT_AND_ROADMAP.md](COMPREHENSIVE_AUDIT_AND_ROADMAP.md) for the full list and sprint plan.  
> Quick additions summarized below have been merged into this master plan to prioritize immediate fixes and next sprints.

---

## Table of Contents
1. [Part A — Critical Fixes (do first)](#part-a--critical-fixes-do-first)
2. [Part B — Structural Improvements](#part-b--structural-improvements)
3. [Part C — 🏆 WOW-Factor Moonshots](#part-c--wow-factor-moonshots)
4. [Part D — Quality, Testing & Ops](#part-d--quality-testing--ops)
5. [Phasing / Sprint Plan](#phasing--sprint-plan)
6. [Jury Demo Script](#jury-demo-script)
7. [Metrics to Prove Impact](#metrics-to-prove-impact)

---

## Part A — Critical Fixes (do first)

These are correctness, trust, and credibility bugs. A jury (or a real ops team) will lose trust the moment they spot fake data or contradictory docs. Clear these before adding anything new.

- [ ] **A1 — Remove the hardcoded absolute path + username.** `backend/app/routes/data.py:28` hardwires `C:\Users\USER\OneDrive\Desktop\coficab\DB\...`. Replace with config/env only; never read a developer-specific path. **(S, ⭐⭐⭐)**
  - Make `WEEKLY_PLANNING_FILE_PATH` the single source; default to the repo `weekly planning/` folder; error clearly if absent.
- [ ] **A2 — Fix the copilot documentation drift.** `README.md:186` and the saved memory say *"Anthropic Claude `claude-opus-4-8`"*; the code (`backend/app/services/copilot_service.py:32`) actually uses **Groq / Llama-3.3-70B**. Decide which is true, then make README, `.env.example`, and memory agree. **(S, ⭐⭐)**
- [ ] **A3 — Kill the silent mock fallback OR label it loudly.** `data.py` falls back to `MOCK_TRANSPORTS` and the frontend ships hardcoded KPIs (`frontend/data/dashboardData.ts:3`). Either remove mocks from production paths, or render a persistent **"DEMO DATA"** banner whenever `meta.used_mock === true`. Never show fabricated numbers as real. **(M, ⭐⭐⭐)**
- [ ] **A4 — Collapse to ONE optimizer.** Delete `VrptwOptimizer` + `VRPTWOptimizer` (`vrptw_optimizer.py`) and the dead wrapper `vrptw_complete_optimizer.py`. Route **every** planning endpoint through `DailyPlanBuilder._solve_global_vrptw`. Remove the misleading "zone-isolation = optimization" docstrings. **(L, 🏆 — biggest ROI)**
  - Re-point `frontend ... generatePlanning()` (`api.ts:158`) and `/api/optimization/planning/generate` to the unified engine.
- [ ] **A5 — One KPI source of truth.** `getKpi()` (`api.ts:61`) hits `/api/metrics/kpi` (ERD table, empty until monthly snapshots); the copilot uses `/api/planning/daily/dashboard`. Pick one; make the dashboard, copilot, and KPI cards read identical numbers. **(M, ⭐⭐⭐)**
- [ ] **A6 — Default role should be `viewer`, not `admin`.** `auth_service.py:65` and `auth.py:93` default a missing role claim to `admin`. Flip to least-privilege. **(S, ⭐⭐⭐ security)**
- [ ] **A7 — Stop re-parsing Excel on every request.** `data.py:79` parses the workbook per call. Add a cached layer (mtime-keyed) or move ingestion to the DB. **(M, ⭐⭐)**
- [ ] **A8 — Adopt Alembic as the only schema path.** Remove `Base.metadata.create_all` from `main.py:43`; run migrations on deploy. **(M, ⭐⭐)**
- [ ] **A9 — Cache the copilot's `get_kpis`.** Today each call re-runs the ~12s solver over HTTP loopback (`copilot_service.py:399`). Cache per (day, plan version); ideally call the service layer directly instead of HTTP. **(M, ⭐⭐)**
- [ ] **A10 — Repo hygiene.** Commit/clean the uncommitted `copilot_service.py`, remove the untracked `backend/_diag_fleet.py` debug script (or move under `scripts/`). **(S, ⭐)**

---

## New Summary Additions (from full audit)

- **Parts E–K added in companion doc:** Technical Debt & Code Quality, Infrastructure & DevOps, User Experience & Product, Performance & Scalability, Security & Compliance, Data & Observability, Integration & APIs. These contain 70+ new action items.  
- **Top immediate extra fixes (do in Sprint 0):**
  - Enable TypeScript `strict` mode and fix types (frontend). **(M)**
  - Change default unauthenticated role to `viewer` (backend). **(S)**
  - Whitelist CORS origins instead of `*`. **(S)**
  - Add DB indexes for frequent queries (e.g., `plan_version`, `mission_demande`). **(S)**
  - Add a visible "DEMO DATA" banner when mock data is used. **(S)**

Refer to [COMPREHENSIVE_AUDIT_AND_ROADMAP.md](COMPREHENSIVE_AUDIT_AND_ROADMAP.md) for the full priority matrix, sprint schedule, and jury demo script.

---

## Part B — Structural Improvements

The architecture is sound; these turn it from "demo" into "product."

- [ ] **B1 — Postgres as the system of record; Excel becomes an ingest event.** The collector agent parses the workbook **once on change** → writes to DB; all endpoints read the DB. Removes the Excel-per-request fragility and the mock fallback entirely. **(L, ⭐⭐⭐)**
- [ ] **B2 — Add a volume / m³ capacity dimension.** Cable reels *cube out* before they weigh out. Today only positions + kg are modeled (`daily_plan_builder.py`), so the solver can produce physically un-loadable trucks. Add `capacity_m3` as a third OR-Tools dimension. **(M, ⭐⭐⭐ — very COFICAB-specific, jury-credible)**
- [ ] **B3 — Make Hours-of-Service a hard constraint, not a warning.** `_hos_warnings` flags 9h/13h *after* solving. Encode driving limits + mandatory breaks (e.g. 45 min after 4.5h) directly in the time dimension so the plan is legal by construction. **(L, ⭐⭐⭐)**
- [ ] **B4 — Time-dependent travel times.** You already integrate OSRM (`_build_matrix`). Replace the single 55 km/h with time-of-day speed profiles (peak vs off-peak). **(L, ⭐⭐)**
- [ ] **B5 — Multi-day rolling plan.** Currently single-day only. Allow deliveries with a date range to be scheduled across the planning horizon to balance fleet load. **(XL, ⭐⭐)**
- [ ] **B6 — Driver–truck assignment optimization.** Today drivers are assigned round-robin (`_assign_driver`). Optimize on skills, licenses, home base, fairness. **(M, ⭐⭐)**
- [ ] **B7 — Consolidate the four planning screens** (`planning`, `daily-planning`, `generated-planning`, `generated-daily-planning`) into one coherent flow. **(M, ⭐⭐ UX)**
- [ ] **B8 — Validate the upstream Excel split syntax.** Free-text `"24pos beja1 8pos beja 2"` is the most error-prone input. Provide a template/validator or a structured split UI so typos can't reach the planner. **(M, ⭐⭐)**

---

## Part C — 🏆 WOW-Factor Moonshots

These are the features that make a jury lean forward. Each is scoped to be **demo-able** and built on top of what already exists. Pick 3–4 and execute them beautifully rather than half-building all of them.

### C1 — 🏆 Self-Healing Live Re-Planning ("Disruption Co-Pilot")
**The wow:** mid-demo, click *"Truck 3 breaks down at 11:40"*. The platform instantly re-optimizes only the **remaining** undelivered stops across the remaining fleet, shows the diff (who absorbs what, new ETAs, added cost/CO₂), and asks for one-click approval.
- **Why it wows:** real logistics pain is *disruption*, not the first plan. Self-healing = "this is a real product."
- **How:** new endpoint `POST /api/planning/replan` that takes (current plan, completed stops, disrupted resource) → re-runs the unified VRPTW on the residual problem → returns a `PlanDiff`. You already have `planning_diff` / `planning_change_log` models to render it.
- **Effort:** L · **Demo time:** 60s · **Build on:** unified optimizer (A4), tracking.

### C2 — 🏆 Digital Twin + Monte-Carlo "Plan Confidence Score"
**The wow:** every plan ships with a **confidence %** ("87% of simulated days finish on time"). Run the day 500× with sampled travel-time/service-time/traffic noise; report P50/P90 finish time, OTIF distribution, and the single most fragile stop ("Kairouan drop is late in 32% of runs — leave 20 min earlier").
- **Why it wows:** turns a deterministic plan into a *risk-aware* decision. Juries love quantified uncertainty.
- **How:** wrap the schedule simulator in a vectorized Monte-Carlo loop; sample from historical (or assumed) delay distributions. Pure compute, no new infra.
- **Effort:** M–L · **Demo time:** 30s · **Build on:** existing scheduler.

### C3 — 🏆 Carbon & ESG Optimizer (Pareto frontier: Cost ↔ Time ↔ CO₂)
**The wow:** a slider that re-optimizes between **cheapest**, **fastest**, and **greenest**, showing a live Pareto curve and the CO₂ saved (kg) vs the manual baseline. Export an **ESG report**.
- **Why it wows:** sustainability is a guaranteed jury hot-button, and COFICAB (automotive supply chain) has real CO₂ reporting pressure from OEM customers.
- **How:** add a CO₂ term (fuel L × emission factor) as a selectable objective weight in `CostConfig`; expose multi-objective runs and plot the trade-off.
- **Effort:** M · **Demo time:** 45s · **Build on:** existing TND cost model (just add the CO₂ axis).

### C4 — 🏆 Agentic Copilot that *Acts* (with human approval)
**The wow:** type *"Béja is overloaded and we're paying for the rental — fix it."* The copilot proposes: *split Béja, drop the rental, re-run* → shows before/after KPIs → you click **Apply**. It executes the change it recommended.
- **Why it wows:** moves from "chatbot that explains" to "co-pilot that does," which is the current frontier narrative.
- **How:** add **write tools** (propose_split, reassign_truck, trigger_replan) that return a *proposed diff* requiring explicit confirmation — never auto-commit. Reuses the disruption replan (C1).
- **Effort:** L · **Demo time:** 60s · **Build on:** copilot tool loop + C1 + planning governance.

### C5 — 🏆 Predictive ETA & Demand Forecasting (the "real AI")
**The wow:** "Tomorrow we predict **41 deliveries / 612 positions** (±8%); you'll need the rental on Thursday." Plus per-stop ETAs **learned from actuals**, not from a fixed speed.
- **Why it wows:** this is where the "intelligent platform" claim finally becomes literally true — it learns.
- **How:** capture planned-vs-actual (you already compute OTIF/OTD); train a light model (gradient boosting / Prophet for demand, residual model for ETA). Even a simple learned correction factor per zone/time-of-day is demonstrably better than 55 km/h flat.
- **Effort:** XL · **Demo time:** 30s · **Build on:** tracking + KPI history (close the feedback loop, B/C synergy).

### C6 — 🏆 Live Control-Tower Map with Geofencing Alerts
**The wow:** a real-time map of trucks moving along their routes; geofence each client; auto-fire an incident the moment a truck is predicted to miss a window — *before* it's late.
- **Why it wows:** the "mission control" visual is instantly impressive on a projector.
- **How:** you already have `TruckMap`, `RouteMap`, tracking endpoints, and an incident service. Add geofence checks + predicted-late detection to the monitor agent and push to the map.
- **Effort:** L · **Demo time:** 45s · **Build on:** existing maps + agents + incidents.

### C7 — 🏆 WhatsApp Driver Channel + Mobile ePOD
**The wow:** the dispatcher hits "Dispatch," and the driver's **WhatsApp** pings with the mission brief (stops, ETAs, a map link). The driver replies with a photo = electronic Proof of Delivery, which flips the stop to *delivered* live on the control tower.
- **Why it wows:** WhatsApp is *the* tool Tunisian drivers actually use. This bridges the "last mile" between the slick dashboard and reality — extremely concrete and relatable.
- **How:** WhatsApp Business / Twilio webhook; you already have `proof`, `dispatch`, and `execution` models/routes.
- **Effort:** L · **Demo time:** 60s (use your own phone live!) · **Build on:** dispatch + proof + execution services.

### C8 — Explainable Routing ("Why this route?") with counterfactuals
**The wow:** click any leg → *"Truck 5 serves Sousse because it's the only truck with ≥24 positions free, and going via Enfidha first saves 18 km / 4.2 kg CO₂. Sending Truck 2 instead would cost +37 TND."*
- **Why it wows:** explainability builds trust and shows the OR depth under the hood.
- **How:** the copilot already has plan context; add a structured "decision rationale" generated from the cost breakdown + a cheap counterfactual re-solve.
- **Effort:** M · **Build on:** copilot + cost model.

### C9 — One-click Executive Report (auto-generated deck/PDF)
**The wow:** "Generate board report" → a polished PDF/slide deck: today's KPIs, CO₂ saved, cost vs manual baseline, exceptions, trend charts.
- **Why it wows:** shows the platform speaks to management, not just dispatchers — closes the value story.
- **Effort:** S–M · **Build on:** existing KPI/metrics endpoints + a templating/export step.

### C10 — "Stress-Test Tomorrow" scenario lab
**The wow:** *"What if we lose 2 trucks?" / "What if volume +30%?"* → instantly see how many deliveries go unassigned, the extra cost, and the rental needed. A planning *what-if* sandbox.
- **Why it wows:** decision-support for capacity planning, not just execution.
- **Effort:** M · **Build on:** unified optimizer (A4) + variant scoring you already do.

---

## Part D — Quality, Testing & Ops

- [ ] **D1 — Rate limiting** on public + LLM endpoints (the copilot can trigger the solver). **(S)**
- [ ] **D2 — Structured logging + a `/metrics` Prometheus endpoint** (requirements promise it; deliver a thin version). **(M)**
- [ ] **D3 — Optimizer regression/golden tests** — lock known inputs → expected plan cost so refactors can't silently regress route quality. **(M)**
- [ ] **D4 — Copilot eval suite** — a fixed set of Q&A with grounded-answer assertions + a prompt-injection test for `query_platform`. **(M)**
- [ ] **D5 — Validate the "impact" claims.** The 15→3 min / 480× detection table (`REQUIREMENTS.md:166`) needs a measurement methodology or should be marked as targets. **(S)**
- [ ] **D6 — Load test** the 500-transport / 1000-req-min NFRs that are currently asserted but unproven. **(M)**

---

## Phasing / Sprint Plan

### Sprint 0 — "Earn trust" (½ week)
A1, A2, A3, A6, A10 — no fake data, honest docs, least-privilege. Cheap, high credibility.

### Sprint 1 — "One brain" (1 week)
A4 (unify optimizer), A5 (one KPI source), A7–A9, B2 (volume dimension). The platform now has a single, correct, COFICAB-credible engine.

### Sprint 2 — "Wow #1: it's alive" (1–1.5 weeks)
C1 (self-healing replan) + C6 (live control tower) + C3 (CO₂/ESG). A live, self-healing, green control tower demos *spectacularly*.

### Sprint 3 — "Wow #2: it's smart" (1.5–2 weeks)
C2 (Monte-Carlo confidence) + C4 (agentic copilot) + C8 (explainability). Risk-aware, acts on its own recommendations, explains itself.

### Sprint 4 — "Wow #3: it touches reality" (1.5 weeks)
C7 (WhatsApp + ePOD) + C5 (predictive ETA/demand) + C9 (exec report). Bridges to drivers, learns from actuals, reports to the board.

> **If you only have time for THREE wow features, pick: C1 (self-healing), C3 (CO₂/ESG), C7 (WhatsApp).** Together they tell a complete story — resilient, sustainable, and real.

---

## Jury Demo Script (≈5 minutes)

1. **(20s) The problem.** "Manual planning takes 15–21 min and ~15% of rows have errors." Show the messy Excel.
2. **(30s) Generate.** Drop the workbook → one click → optimized multi-truck plan in seconds, with cost in TND **and** CO₂.
3. **(30s) Confidence (C2).** "This plan finishes on time in 87% of simulated days; the Kairouan stop is the fragile one." → quantified risk.
4. **(45s) Sustainability (C3).** Drag the slider cost→green; watch CO₂ drop on the Pareto curve. Export the ESG report (C9).
5. **(60s) Disruption (C1).** "Truck 3 just broke down." → self-healing replan, show the diff and the new ETAs.
6. **(60s) Talk to it (C4 + C8).** "Why is Truck 5 going to Sousse?" → it explains. "Drop the rental." → it proposes and you Apply.
7. **(45s) Reality (C7).** Hit Dispatch → **your own phone** buzzes on WhatsApp with the mission. Reply with a photo → the stop flips to *delivered* on the live map (C6).
8. **(20s) The close.** KPI dashboard: minutes not hours, near-zero errors, X kg CO₂ saved, Y TND saved vs manual.

> The arc — **fast → risk-aware → green → resilient → conversational → real** — is what produces the *wooow*.

---

## Metrics to Prove Impact

Don't just claim improvement — instrument it and show the delta on screen:

| Metric | Baseline (manual) | Target | How measured |
|--------|-------------------|--------|--------------|
| Planning time | 15–21 min | < 30 s | wall-clock on `generate` |
| Data error rate | ~12–18% | < 1% | validation warnings / total rows |
| Fleet utilization | ? | +10–15% | positions used ÷ capacity |
| Cost per plan (TND) | manual baseline | −X% | `estimated_cost_tnd` vs baseline |
| CO₂ per plan (kg) | manual baseline | −X% | fuel × emission factor |
| On-time (OTIF) | ? | +X pts | planned vs actual arrival |
| Disruption recovery | hours (manual) | < 10 s | replan latency (C1) |

---

*Generated from a full-codebase audit. Keep this file updated as items land — check the boxes, and the roadmap doubles as your progress log.*
