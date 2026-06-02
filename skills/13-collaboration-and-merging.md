# 13 — Collaboration & Autonomous Merging

> Goal: let multiple collaborators (humans + AI agents) work on the platform in parallel without breaking the KPI scoring contract or the frozen UI. Define what can merge automatically, what needs a human, and how conflicts get resolved without information loss.

---

## Applicability by team size

Not all sections of this skill apply at every stage. Use the table below to decide what to adopt:

| Context | Adopt | Skip |
|---|---|---|
| Solo developer | §1 branching model, §4 PR template, §6 CI gates | §2–3 merge tiers, §5 CODEOWNERS |
| Two humans | §1, §4, §6 + §3 conflict resolution rules | §2 autonomous-agent logic |
| Human + AI agent committing code | All sections | — |

**For a PFE project with one or two contributors:** start with §1 (branching), §4 (PR template), and §6 (CI gates). They cost almost nothing and prevent the most common mistakes (long-lived branches, missing KPI regression signal). Add §2–3 only when an autonomous agent is actively pushing commits.

---

## KPI anchor
Indirect, but the most important reason this skill exists:
- The **scoring system** (skill 01) is the platform's contract. A bad merge that silently changes a formula or a color band corrupts every report from that day forward.
- The **frontend visual identity** is the platform's voice. A bad merge that "improves" a card style breaks the do-not-touch rule from skill 09.

These two surfaces are protected with explicit tiers below.

---

## 1. Branching model — trunk-based, short branches

```
main                ── always green, deployable
 ├── feat/...       ── short-lived (< 3 days), one feature or one skill at a time
 ├── fix/...        ── bug fixes, even shorter
 └── chore/...      ── lint, deps, docs
```

Rules:
- Branch from `main`. Rebase onto `main` before pushing, every day.
- Push at least daily, even if the work is incomplete (WIP marker).
- PR opens early as **draft**. Convert to ready when CI is green and the verification checklist (skill 12) is complete.
- One PR ≤ ~400 lines of real diff (excluding generated files, snapshots, lockfiles). Bigger PRs get rejected and re-split.

Why this works on a project of this size: short branches mean small conflicts. Small conflicts almost always resolve cleanly via the rules below.

---

## 2. Merge tiers — what an agent may decide alone

Every change is classified into one of four tiers. Higher tier = more humans required.

### TIER A — Autonomous merge, no review

The agent may rebase, resolve, and merge on its own.

- Formatting / Prettier / Black / `ruff format` output.
- Comments, docstrings, README typos.
- Test additions that don't change tested behavior.
- New fixtures, factory functions, demo seed rows.
- Lockfile churn (`package-lock.json`, `poetry.lock`) when the manifest is unchanged.
- Tailwind class re-ordering inside the same className (cosmetic, no visual change).
- Adding a new `kpi_definition` row for a new code (existing codes untouched).
- Adding a new SWR hook in `frontend/hooks/` that calls an endpoint that already exists.

### TIER B — Autonomous merge IF the validation suite passes

Merge once `pytest` is green AND `npm run build` succeeds AND the dashboard renders (skill 12 checklist run by CI or manually).

- New API routes (no breaking changes to existing endpoints).
- New columns added (nullable, with default) to existing tables.
- New tables.
- New frontend pages or components that are not yet linked from the sidebar.
- Replacing a mock-data import with an SWR hook on a page (skill 09 migration).
- Refactors that preserve public function signatures.
- Dependency bumps within semver minor.

The agent runs the verification, posts the result in the PR, and merges if green.

### TIER C — Human review required (one approver)

The agent may write and push, but **must not merge** until a designated reviewer approves.

- Edits to `KpiService` (any compute_* method body).
- Edits to `kpi_definition` rows (thresholds, target, direction).
- Schema migrations that alter an existing column type or constraint.
- Changes to `plan_version` lifecycle transitions (skill 05).
- Frontend palette tokens, sidebar gradient, card classes.
- Replacing or upgrading a charting library (don't — but if you must, TIER C).
- Auth flow or role definitions.

### TIER D — Blocked. Requires explicit override.

The agent must propose a TIER D change as a PR, mark it **blocked**, and tag both the project owner and at least one data steward in the description. No automated merge under any circumstances.

- Removing a KPI from the catalog.
- Dropping or renaming a column on `plan_mission`, `demandes_local`, `evenement_alea`, or any `kpi_*` table.
- Mutating rows in a `plan_version` whose `statut_plan = 'VALIDE'`.
- Deleting `planning_change_log` entries (audit trail is immutable).
- Deleting `notification_log` entries.
- Bypassing `KpiService.color_for()` to hardcode a band somewhere else.
- Bumping a dependency across a major version.
- Anything touching `frontend/components/layout/Sidebar.jsx` or the gradient class.

---

## 3. Conflict resolution rules (autonomous)

When the agent rebases or merges and Git reports a conflict, apply these rules in order. The agent may resolve a TIER A/B conflict on its own; TIER C/D conflicts must be flagged.

### Rule 1 — Append, don't overwrite (catalog files)

For "registry" files — `kpi_definition` seed, ENUM lists, route mounts in `main.py`, sidebar nav array — if both sides added entries, **keep both**. Order alphabetically or by domain block, never alphabetically across boundaries.

```python
# main.py — both sides added a router
<<<<<<< ours
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
=======
app.include_router(fleet.router, prefix="/api/fleet", tags=["fleet"])
>>>>>>> theirs
```
Resolution: keep both, in domain order.

### Rule 2 — Migrations are append-only

Never edit a committed migration. If two branches added migrations with overlapping version numbers, the second to merge renames its file to the next free number. Schema diffs are reconciled by writing a follow-up migration if needed — never by altering the prior one.

### Rule 3 — KPI formula conflicts → freeze and ask

If both sides edited the same `KpiService.compute_*` body, the agent **does not pick a winner**. It writes a comment in the PR with both versions side-by-side, links to skill 01 (the spec source), and tags a reviewer. Default fallback: the version that has passing tests against the fixtures in skill 12.

### Rule 4 — Frontend mock-data deletions

If branch A migrated `dashboard/page.jsx` to use `useKpi`, and branch B added a new field to `dashboardData.ts`, the **API path wins**:
- Apply A's migration.
- Re-add B's field to the API response (extend the backend's payload, or extend the adapter in `useKpi`).
- Mock file is left in place until **every page** migrated.

### Rule 5 — UI conflicts → palette wins

If both sides edited a JSX file and one introduces a non-palette color, the palette wins. The agent reverts the off-palette change and posts the diff to the PR.

### Rule 6 — Test file conflicts

Tests are append-only too. Two branches adding new tests → keep both. Two branches modifying the **same** test → the more strict assertion wins. Same logic as catalog rule 1: prefer union.

### Rule 7 — Generated files

`package-lock.json`, `poetry.lock`, build artifacts: regenerate from the manifest after merging. Do not attempt to hand-resolve.

```bash
git checkout --theirs package-lock.json && npm install
git checkout --theirs poetry.lock && poetry lock --no-update
```

### Rule 8 — Tie-breakers

If two rules apply and disagree, pick the rule that is **more conservative** (preserves more information / requires more review). In doubt → don't merge, flag.

---

## 4. PR template (mandatory)

Place at `.github/pull_request_template.md`:

```markdown
## What

(One sentence. The user-facing change.)

## Why

(Link to the skill or issue.)

## KPI impact

- Indicator(s) affected: [ ] R4-06  [ ] R4-02  [ ] R4-13  [ ] R5-10  [ ] R4-02-PF  [ ] R4-03  [ ] R4-12  [ ] R4  [ ] None
- Direction of impact: improves / neutral / risks regression
- Verification: (which KPI test in skill 12 was rerun?)

## UI impact

- [ ] Pixel-identical to current dashboard (screenshot below)
- [ ] Visual change — palette/layout edit (TIER C, requires UI lead approval)

## Tier

- [ ] A — autonomous merge OK
- [ ] B — autonomous merge after CI green
- [ ] C — human approver required
- [ ] D — blocked, explicit override needed

## Rollback plan

(How to revert if a KPI regresses post-merge.)
```

Agents fill this in; humans verify and check the tier. **A PR without a tier is auto-tagged TIER C** until someone classifies it.

---

## 5. CODEOWNERS — who guards what

`.github/CODEOWNERS`:

```
# Default: project owner
*                                       @ghada

# KPI scoring system — data steward only
/coficab_platform/backend/app/services/kpi_service.py     @data-steward
/coficab_platform/backend/app/agents/kpi_jobs.py          @data-steward
/coficab_platform/database/seed_kpi_definitions.sql       @data-steward
/coficab_platform/skills/01-scoring-system.md             @data-steward
/coficab_platform/skills/reference/kpi-formulas.md        @data-steward

# Schema — backend lead + data steward
/coficab_platform/database/schema.sql                     @backend-lead @data-steward
/coficab_platform/backend/app/models/                     @backend-lead

# Frontend visual identity — UI lead
/coficab_platform/frontend/tailwind.config.js             @ui-lead
/coficab_platform/frontend/app/globals.css                @ui-lead
/coficab_platform/frontend/components/layout/             @ui-lead
/coficab_platform/skills/reference/ui-conventions.md      @ui-lead

# Skills folder — owner + the affected discipline
/coficab_platform/skills/                                 @ghada
```

Replace handles with real GitHub usernames. CODEOWNERS makes TIER C protection automatic on GitHub.

---

## 6. Pre-merge gates (CI)

`.github/workflows/ci.yml` should fail the merge unless **all** are green:

```yaml
- name: Backend tests
  run: pytest backend/tests -v --tb=short

- name: KPI invariant suite
  run: pytest backend/tests/unit/test_kpi_*.py -v

- name: Frontend build
  run: npm --prefix frontend ci && npm --prefix frontend run build

- name: Schema migration applies cleanly
  run: psql $TEST_DB -f database/schema.sql

- name: Lint
  run: ruff check backend/ && npm --prefix frontend run lint
```

The **KPI invariant suite** is a copy of skill 12's eight tests, run separately so a KPI regression is immediately obvious in the CI output ("R4-06 expected 92.54, got 88.10").

---

## 7. Agent autonomy contract

When an AI agent makes changes in this repo, it must:

1. **Declare the tier** at the start of every PR description.
2. **Show its work**: link to the skill section that justifies the change.
3. **Never edit two tiers in one PR**. Split a refactor that touches both a TIER A docstring and a TIER C formula into two PRs.
4. **Self-rollback**: if a post-merge KPI snapshot regresses by > 5% vs the previous day without a documented cause, revert the merge automatically and open a new draft PR for review.
5. **Surface uncertainty**: if a conflict resolution rule is unclear, tag the owner with a one-line summary instead of guessing.

---

## 8. Communication artifacts (low-overhead)

| Artifact | Purpose | Where |
|---|---|---|
| PR description | Tier, KPI impact, rollback | GitHub |
| Commit message | What + why, ≤ 72 char subject | `git log` |
| `CHANGELOG.md` | User-visible changes per release | repo root |
| Skill update | If a behavior diverges from a skill, the skill is updated **in the same PR** | `coficab_platform/skills/` |

Do **not** introduce: a separate decision-log doc, an architecture-decision-record (ADR) folder, a Notion mirror. The skills folder IS the decision log; keep it as the single source.

---

## 9. Recovery procedures

### A KPI regressed after a merge
1. Open the offending commit. Identify the formula or query that changed.
2. Revert with `git revert <sha>`. Push a TIER A revert PR (auto-merge).
3. Run `backend/scripts/recompute_kpis.py --from <date> --to <today>`.
4. Confirm dashboard matches the pre-regression baseline.

### Two collaborators created conflicting `plan_version` rows
This is a data conflict, not a code conflict. Both rows are kept (`plan_id` differs by design). The planner picks the version to validate; the loser stays as DRAFT for audit.

### A migration was committed to `main` that breaks deploy
1. Author opens a **follow-up** migration that reverses the change (never edit the broken one).
2. The follow-up is TIER C: backend lead must approve.
3. After merge, run both migrations in order on staging before prod.

### A `VALIDE` plan_version was mutated by accident
1. This should be impossible — the validation handler enforces immutability. If it happened, there's a bug.
2. Open a TIER D PR documenting the breach.
3. Restore the row from the most recent DB backup or from `planning_change_log` if the diff is small.
4. Fix the handler.

---

## 10. Anti-patterns

- ❌ Long-lived feature branches. They turn every rebase into a multi-hour archaeology project.
- ❌ Force-pushing to `main` to "fix history". Revert publicly instead.
- ❌ Merging your own PR without CI green or without checking the tier.
- ❌ Editing a committed migration "just to clean it up". Always write a follow-up.
- ❌ Resolving a TIER C/D conflict by picking one side silently. Flag and wait.
- ❌ Stuffing unrelated changes into the same PR to "save a round-trip". Split.
- ❌ Skipping the PR template because "it's a small change". Five seconds of typing prevents a multi-day investigation later.

---

## 11. Verification

1. Open two branches that both add a row to `kpi_definition`. Merge one, rebase the other → conflict resolved by Rule 1 (both rows kept).
2. Open a PR that edits `KpiService.compute_otif` without a TIER C reviewer. CODEOWNERS auto-blocks merge. Confirm.
3. Push a frontend change that introduces a non-palette color. Lint or visual review flags it.
4. Open a TIER A PR (typo fix). CI runs, merges automatically.
5. Introduce a deliberate KPI regression in a feature branch. The CI invariant suite fails. Merge is blocked.

If all five behave as expected, the collaboration layer is working.
