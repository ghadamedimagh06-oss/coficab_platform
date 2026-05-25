# Reference — Conflict Resolution Matrix

Quick lookup for the **autonomous merge agent** (or a human in a hurry). Cross the row (kind of change) with the column (kind of conflict) → get an action.

For the full policy and rationale, see skill [`13-collaboration-and-merging.md`](../13-collaboration-and-merging.md).

---

## Tier at a glance

| Tier | Decision | Examples |
|---|---|---|
| **A** | Auto-merge | typos, formatting, lockfiles, new fixtures, new `kpi_definition` codes |
| **B** | Auto-merge after CI green | new routes, new tables, additive columns, new SWR hooks, page migrations |
| **C** | Human approver required | KPI formula edits, threshold changes, lifecycle transitions, palette/sidebar |
| **D** | Blocked / explicit override | KPI removal, dropping audit columns, mutating VALIDÉ plans, major dep bump |

---

## Conflict resolution lookup

### A. Catalog / registry files (sidebar nav, ENUMs, KPI seed, router list)

| Conflict shape | Resolution | Tier |
|---|---|---|
| Both sides added different entries | **Keep both**, sorted by domain | A |
| Both sides added the **same** entry with different values | Tag reviewer, prefer the version with a referenced skill / test | C |
| One side removed an entry the other extended | Keep the entry, drop the removal (assume regression) | C |

### B. Database schema & migrations

| Conflict shape | Resolution | Tier |
|---|---|---|
| Two new migration files with same version number | Rename the later one to next free slot | A |
| Both sides edited a **committed** migration | Reject — only follow-up migrations allowed | D |
| Both sides added a new column to the same table | Keep both columns | B |
| One side dropped a column the other queries | Block, restore column, tag data steward | D |
| Both sides changed the same column type | Pick the more permissive type, run conversion in a new migration | C |

### C. KPI logic (`KpiService`, `kpi_definition`, formulas in skills)

| Conflict shape | Resolution | Tier |
|---|---|---|
| Both sides edited the same `compute_*` body | Do NOT pick a winner — flag reviewer, attach side-by-side diff | C |
| One side updated the formula, the other updated the test fixture | Apply both, re-run skill 12 test suite — if it stays green, merge | C |
| Both sides changed a band threshold | Prefer the value matching the spec image (skill 01 §1). If both diverge → block | C / D |
| One side adds a new KPI code, other refactors `compute_*` helper | Apply both, the new code uses the helper | B |

### D. Backend routes / services

| Conflict shape | Resolution | Tier |
|---|---|---|
| Two new endpoints in the same router | Keep both | B |
| Same endpoint, different bodies | Prefer the side with newer signature in `reference/api-contracts.md`, ask if neither | C |
| Both sides edited error-handling on the same handler | Take the stricter validation, merge messages | B |
| One side changed an endpoint's response shape | Block until frontend consumers are migrated | C |

### E. Frontend pages and components

| Conflict shape | Resolution | Tier |
|---|---|---|
| Both sides edited the same `.jsx` with palette-compliant changes | Three-way merge, run dashboard visually | B |
| One side introduced a non-palette color | Revert that change automatically (palette wins) | A |
| Both sides reshaped a card layout | Block, UI-lead review | C |
| Mock data deletion vs. new mock field | API path wins — extend backend payload, keep mock present | B |
| Sidebar gradient touched | Block | D |

### F. Tests

| Conflict shape | Resolution | Tier |
|---|---|---|
| Two new tests added | Keep both | A |
| Same test edited differently | Use the stricter assertion | B |
| One side deleted a test the other strengthened | Keep the strengthened version | B |
| Removing a KPI invariant test | Block | D |

### G. Generated / lock files

| Conflict shape | Resolution | Tier |
|---|---|---|
| `package-lock.json` | `git checkout --theirs` then `npm install` | A |
| `poetry.lock` | `git checkout --theirs` then `poetry lock --no-update` | A |
| Coverage / build artifacts | Regenerate, don't merge by hand | A |

### H. Documentation / skills

| Conflict shape | Resolution | Tier |
|---|---|---|
| Both sides edited same skill section | Keep the version with the most recent fact (later commit date), merge unique paragraphs | B |
| Skill update without matching code change | Block until code & skill match | C |
| `reference/ui-conventions.md` palette table edited | Block | D |
| `reference/kpi-formulas.md` formula edited | Block | C |

---

## Three short checks before merging (any conflict)

1. **CI green?** No → fix or rollback. Don't merge red.
2. **KPI snapshot reproduces?** Run skill 12's eight tests against the merge commit; values must match. No → flag.
3. **Dashboard renders?** `npm run build` + visual eyeball at `/dashboard`. No → flag.

If all three pass and the conflict was Tier A or B per the table, merge.

---

## Override syntax (TIER D)

A TIER D merge needs explicit human override. The merge commit message must include the literal line:

```
TIER-D-OVERRIDE: <one-sentence justification>  by <github-handle>
```

CI inspects the merge message; if the line is missing, the deploy job refuses to pick up the commit. The handle must belong to a CODEOWNER of the touched files.

---

## Worked examples

**Example 1 — two branches add a KPI**
- Branch `feat/r4-14`: adds `R4-14 Driver Hours` to `kpi_definition` seed + new `compute_driver_hours`.
- Branch `feat/r4-15`: adds `R4-15 Truck Idle Time` similarly.

→ Both seeds conflict in the same `INSERT` block.
→ Rule A.1 — Keep both. Order by code. New `compute_*` methods don't conflict.
→ Tier B (additive). Merge after CI.

**Example 2 — formula change + UI swap**
- Branch `fix/otd-formula`: replaces row-weighted with quantity-weighted in `compute_otd`.
- Branch `feat/dashboard-api`: migrates `dashboard/page.jsx` from mock to `useKpi`.

→ No file conflict.
→ Tier mix: C (formula) + B (UI wiring). Split would have been cleaner, but possible to merge sequentially. Merge B first (independent), then C with reviewer approval. Re-run KPI tests after each merge.

**Example 3 — incompatible UI edits**
- Branch `feat/nicer-cards`: changes `bg-white rounded-2xl` to `bg-gradient-to-br ...`.
- Branch `feat/accent-stripe`: adds the allowed `border-l-4 border-l-emerald-500`.

→ Conflict in `StatCard.jsx`.
→ Rule E.2 — `bg-gradient` is off-palette. Revert it. Keep `accent-stripe`.
→ Tier D notice opened for the gradient change so the author understands why.

**Example 4 — migration version collision**
- Branch `feat/notif-log`: `0007_add_notification_log.sql`.
- Branch `feat/audit-cause`: `0007_add_evenement_cause.sql`.

→ Filename conflict.
→ Rule B.1 — rename the second-to-merge to `0008_...`.
→ Tier A.

---

## When the matrix doesn't answer

Don't guess. Tag the project owner, link this matrix, describe the conflict in two sentences. Better to wait an hour for a clear decision than to corrupt the KPI pipeline.
