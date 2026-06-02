# Coficab Transport Platform — Skills Index

This folder is the **implementation playbook** for finishing the Coficab AI Transport Platform. Each skill is a focused, self-contained module that an AI agent (or a developer) can read and execute without needing the rest of the conversation.

---

## How to use this folder

1. Read [`00-architecture-overview.md`](00-architecture-overview.md) first to understand the system map and the optimizations being applied to the current codebase.
2. Treat [`01-scoring-system.md`](01-scoring-system.md) as the **single source of truth** for every business decision. Every other skill references it.
3. Pick the skill that matches the feature you're building. Each skill is self-contained: files to touch, code to write, KPI impact, verification steps.
4. Use [`reference/`](reference/) for lookups (formulas, API contracts, ERD, UI rules).

> **Code snippets in skill files are reference implementations, not the authoritative source.**
> The canonical code lives in the repository. If a skill's snippet diverges from what's in the repo,
> **trust the repo** and update the skill. Update the skill when the *spec* changes; update the code when the *implementation* changes.

---

## Skill catalog

| # | Skill | KPI anchor | Status |
|---|---|---|---|
| 00 | [Architecture overview](00-architecture-overview.md) | (cross-cutting) | foundation |
| 01 | [**Scoring system**](01-scoring-system.md) | **all R4 & R5 KPIs** | **anchor** |
| 02 | [Database schema](02-database-schema.md) | feeds every KPI | foundation |
| 03 | [Data ingestion](03-data-ingestion.md) | feeds OTD / OTIF / Load Eff | inbound |
| 04 | [VRPTW optimization](04-vrptw-optimization.md) | Load Eff, Fuel, Logistics Cost | core |
| 05 | [Plan validation (human-in-the-loop)](05-plan-validation.md) | OTD, Premium Freight | core |
| 06 | [Driver dispatch & notifications](06-driver-dispatch.md) | OTD, OTIF | execution |
| 07 | [Incident & alea tracking](07-incident-tracking.md) | Customer Logistics Incidents/MKm | feedback |
| 08 | [KPI computation jobs](08-kpi-computation-jobs.md) | snapshots all KPIs daily/monthly | feedback |
| 09 | [Frontend wiring (UI unchanged)](09-frontend-wiring.md) | exposes every KPI to UI | presentation |
| 10 | [Real-time monitoring](10-realtime-monitoring.md) | OTD risk, incidents | execution |
| 11 | [Auth & roles](11-auth-and-permissions.md) | (governance) | foundation |
| 12 | [Testing & verification](12-testing-and-verification.md) | every KPI | quality |
| 13 | [Collaboration & autonomous merging](13-collaboration-and-merging.md) | protects scoring + UI | governance |
| 14 | [Generated daily planning (Gantt editor)](14-generated-daily-planning.md) | Load Eff, OTD (edit-time only) | partial — Gantt renders; drag-and-drop / export pending |

---

## Reference docs

- [`reference/kpi-formulas.md`](reference/kpi-formulas.md) — exact formulas, units, thresholds, color bands (green / yellow / red).
- [`reference/api-contracts.md`](reference/api-contracts.md) — every backend endpoint, its request/response, which KPI it feeds.
- [`reference/db-erd.md`](reference/db-erd.md) — relational diagram in text form, FK map.
- [`reference/ui-conventions.md`](reference/ui-conventions.md) — exact palette, do's & don'ts. The UI must NOT change visually.
- [`reference/conflict-resolution-matrix.md`](reference/conflict-resolution-matrix.md) — quick lookup: which conflict gets auto-merged, which needs a human, which is blocked.

---

## Six rules that override everything else

1. **Do not change the visual identity of the frontend.** Same purple `#7c3aed` brand gradient, same card layout, same Recharts components, same Lucide icons. Only swap mock data for real API calls.
2. **Every backend write must feed a KPI.** A delivery completes → `kpi_journalier` updates OTD. A truck rolls → fuel & km feed R4-13. An incident is logged → R4-12 updates. If a feature touches data but doesn't move a KPI, it's incomplete.
3. **Keep it boring.** No microservices, no Kafka, no event bus. FastAPI + PostgreSQL + Next.js + APScheduler. The four "agents" are just scheduled jobs in the same backend process — see skill 00.
4. **Plan versions are immutable once `VALIDÉ`.** Editing a validated plan creates a new version. This guarantees audit traceability (required by the spec).
5. **AI proposes, human approves.** No automatic dispatch. The transport manager must click "Valider" before drivers are notified.
6. **No silent merges across tiers.** KPI formulas, schema migrations on existing columns, and the frontend palette are protected — see skill [13](13-collaboration-and-merging.md) and the [conflict-resolution matrix](reference/conflict-resolution-matrix.md). Autonomous agents merge TIER A/B only.

---

## Where to start (build order)

If you're picking up this project fresh, follow this order:

```
02 (schema)
  → 01 (KPI scoring tables + seed kpi_definition with R4/R5 codes)
    → 03 (ingestion → demandes_local)
      → 04 (VRPTW → plan_mission)
        → 05 (validation → plan_version status)
          → 06 (dispatch → driver notifications)
            → 07 (incidents → evenement_alea)
              → 08 (KPI jobs aggregate everything)
                → 09 (frontend reads the KPI endpoints)
                  → 10 (real-time live updates)
                    → 12 (verify each KPI cell on the dashboard matches DB)
```

Skill 11 (auth): wire the `get_current_user` FastAPI dependency stub to **all routers before implementing skill 03**. User management (CRUD, role enforcement) can be deferred, but auth retrofitting always misses endpoints — do the stub first. See skill 11 for the two-line stub that unblocks all other skills.
Skill 13 (collaboration & merging) should be in place **before** the second collaborator joins — it defines the autonomous-merge rules and the protected surfaces.
