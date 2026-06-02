# 14 — Generated Daily Planning (interactive Gantt + Excel round-trip)

> Goal: a new page **`/generated-daily-planning`** that takes the weekly Excel
> planning, runs the VRPTW optimizer for one calendar day, and renders the
> result as a **truck × time Gantt** the dispatcher can edit by drag-and-drop,
> then exports back to an Excel sheet **with the same column layout as the
> source** — without ever mutating the original file.

This skill complements:
- skill [04 — VRPTW optimization](04-vrptw-optimization.md) — reuse the solver as the seed generator.
- skill [05 — Plan validation](05-plan-validation.md) — validation/audit is unchanged; this page produces a `DRAFT` plan and lets the user mutate it before submitting.
- skill [09 — Frontend wiring](09-frontend-wiring.md) — same palette, same Lucide icons, no new visual identity.

---

## Current implementation status

Audited against the repository on 2026-06-02. The interactive Gantt and Excel
round-trip are implemented; the next follow-up is integration with the main
plan-validation/save-draft flow from skill 05.

| Feature | Status | Notes |
|---|---|---|
| `/generated-daily-planning` route + page scaffold | ✅ done | |
| Day picker UI | ✅ done | |
| Gantt grid (trucks × time axis 08:00–17:00) | ✅ done | `GanttBoard`, `TimeAxis`, and `TruckLane` |
| Delivery blocks rendered per truck | ✅ done | |
| "Regenerate" button → re-runs optimizer for selected day | ✅ done | |
| Drag-and-drop block reassignment (truck row / time slot) | ✅ done | `@dnd-kit/core`, snapped to a 15-min grid |
| Resize handles (edit ETD/ETA of a block) | ✅ done | start/end pointer handles with 30-min minimum duration |
| Right-click cancel + one-click re-add | ✅ done | marks `cancelled`; restore available from block and constraints panel |
| "Add delivery" panel (client, qty, window, priority) | ✅ done | `AddDeliveryModal` mutates client state |
| Constraints sidebar (per-delivery hard constraints from Excel) | ✅ done | `ConstraintsPanel`; required truck/window checks enforced on edits |
| Export to Excel (same column layout as source, new filename) | ✅ done | `/api/planning/daily/export` + `excel_exporter.py`; source-preservation test exists |

**Do not re-implement the rows above.** Keep them regression-free and continue from the save-draft / validation integration follow-up.

---

## 1. What the page must do

Per the dispatcher's sketch (one row per truck, x-axis = time 08:00 → 17:00,
colored blocks = deliveries grouped into round-trips between hatched
departure/arrival markers at the Coficab depot):

| Capability | Source of truth | Mutates source xlsx? |
|---|---|---|
| Pick a day → auto-generate a plan | VRPTW optimizer over rows for that date | No |
| See each truck as a horizontal timeline (08:00–17:00 default, configurable) | Client state seeded from the generated plan | — |
| Each delivery is a draggable block labelled by **client** (Cofatt, Aptiv, Valeo, Leoni, …) | Client state | — |
| Drag a block to another truck row or another time slot | Client state, snapped to 15-min grid | — |
| A block spans `[ETD, ETA]`; resize handles edit the window | Client state | — |
| Hatched departure/arrival markers at start and end of each round-trip, oriented "to Coficab" on return | Derived from grouping consecutive blocks under the same truck | — |
| Cancel a delivery (right-click / × on the block) | Client state — marked `cancelled` not deleted, so re-add is one click | — |
| Add a new delivery via "+ Add delivery" panel (client, qty, window, priority…) | Client state | — |
| Constraints sidebar: per-delivery hard constraints parsed from the Excel | Read-only, from Excel row | — |
| Export to Excel with the **exact same column layout** as the source | New file `Weekly Delivery planning W{week}_edited_{timestamp}.xlsx` | No — writes a new file |

The five rules from [skills/README.md](README.md) apply — most importantly:
**do not change the visual identity**, and **AI proposes, human approves**.

---

## 2. UX & layout

ASCII of the target page (matches the sketch):

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Generated Daily Planning                  [Day ▼ 2026-05-25] [Regenerate]│
│  Auto-generated from weekly file · Last seed: 14:02 · 23 deliveries       │
├──────────────────────────────────────────────────────────────────────────┤
│ Time →   08  09  10  11  12  13  14  15  16  17                          │
│ ┌──────┬───────────────────────────────────────────────────────────────┐ │
│ │Truck1│ ║▓Cofatt▓▒Aptiv▒█Valeo█║       ║▒Aptiv▒█Valeo█▓Leoni▓║         │ │
│ │Truck2│ ║██Aptiv██║                                                    │ │
│ │Truck3│         ─ ─ ─ ─ ─ ─ ─ ─ ─ (idle)                              │ │
│ │ ...  │                                                                │ │
│ │Truck7│                                                                │ │
│ │Rented│ ║▓New delivery▓║                                              │ │
│ └──────┴───────────────────────────────────────────────────────────────┘ │
│ Legend: ║ departure · ║ arrival to Coficab   [+ Add delivery] [Export ↓] │
├──────────────────────────────────────────────────────────────────────────┤
│ Constraints panel (right-rail, sticky)                                    │
│ • Cofatt #R12 — window 08:00–10:30, priority HIGH, fixed Truck1, 1.4 t   │
│ • Aptiv  #R13 — window any, priority NORMAL, 0.6 t                       │
│ • …                                                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Palette:** brand purple `#7c3aed` for the action bar, neutral `#f8f7f3`
  page background, white cards, `#e8e5df` borders (matches
  [reference/ui-conventions.md](reference/ui-conventions.md)).
- **Block colour:** one stable colour per client name (hash → palette of 8
  pastel hues). Hatched red bars = depot departure/arrival (matches sketch).
- **Snap:** 15-minute grid, blocks have a minimum width of 30 min.
- **Read-only states:**
    - Past plan (date < today) is read-only with a banner.
    - A delivery whose source row has a **hard constraint** (fixed truck or
      fixed time) shows a small lock icon and refuses drops that violate it,
      with an inline reason ("Truck1 only" / "Window 08:00–10:30 required").

---

## 3. Data model — what flows where

### 3.1 Server → client (seed plan)

```ts
type GeneratedPlan = {
  plan_id: number;            // PlanVersion.id (DRAFT)
  day: string;                // ISO date
  trucks: TruckLane[];
  unassigned: Delivery[];     // deliveries the solver could not place
};

type TruckLane = {
  truck_id: number;
  truck_label: string;        // "Truck 1", or registration plate
  capacity_kg: number;
  trips: Trip[];              // each round trip = depot→stops→depot
};

type Trip = {
  trip_id: string;            // client-generated uuid; stable across edits
  depart_at: string;          // "08:00"
  return_at: string;          // "10:45"
  stops: Delivery[];          // in stop order
};

type Delivery = {
  id: number;                 // row_number from Excel
  client: string;             // "Cofatt"
  start_location: string;
  end_location: string;
  quantity_kg: number;
  etd: string | null;         // hh:mm
  eta: string | null;
  priority: 'urgent' | 'high' | 'normal' | 'low';
  status: 'planned' | 'cancelled' | 'new';
  constraints: DeliveryConstraint;
  raw: Record<string, unknown>; // verbatim Excel row, used on export
};

type DeliveryConstraint = {
  required_truck_id?: number;     // from `vehicle` column if non-empty
  required_driver?: string;       // from `driver` column if non-empty
  required_date?: string;
  time_window?: [string, string]; // from etd/eta if both present
  notes?: string;
};
```

### 3.2 Client → server (on Export only)

```ts
type ExportRequest = {
  source_file: string;        // e.g. "Weekly Delivery planning W0526.xlsx"
  day: string;
  plan: GeneratedPlan;
};
// Response: { download_url: string, file_name: string }
```

Edits live **only in React state** between Regenerate and Export. There is no
PATCH per drag — that would create churn in `plan_mission`. The dispatcher
explicitly clicks **Save as draft** (writes a new `PlanVersion` row, status
`DRAFT`) or **Export** (writes the xlsx) when they are happy. This matches the
spec's *AI proposes, human approves* rule.

---

## 4. Backend changes

### 4.1 New file — `backend/app/services/daily_plan_builder.py`

Thin orchestrator that:
1. reads the source xlsx via the existing `PlanningService.parse_weekly_planning`,
2. filters rows for the requested day,
3. parses **per-row constraints** from the existing columns (see §4.3),
4. calls `VrptwOptimizer.plan(day)` (skill 04) or, if the DB is not seeded,
   falls back to a **pure-Python greedy builder** (below),
5. groups consecutive stops between depot returns into `Trip` objects,
6. returns a `GeneratedPlan` JSON.

**Greedy fallback** (used when the DB is empty — current dev state):

```
sort deliveries by (priority desc, etd asc, quantity desc)
for each delivery:
    pick the first truck where:
        - capacity_kg + delivery.qty ≤ truck.capacity_kg for the current trip
        - current trip end + travel_to(delivery) + service ≤ work_window_end
        - required_truck_id constraint, if any, is satisfied
        - time_window constraint, if any, is satisfied
    if no truck fits → trucks.push(rented_truck) once, retry; else → unassigned
    if current trip is "full" → close trip (insert depot return), open next
```

This is intentionally boring (per rule 3 in [README.md](README.md#five-rules-that-override-everything-else)). The OR-Tools path stays as the
primary; greedy is the offline-dev path.

### 4.2 New file — `backend/app/services/excel_exporter.py`

```python
def export_plan_to_xlsx(source_path: Path, plan: dict, out_dir: Path) -> Path:
    """
    Copy the source workbook to a new file, then overwrite the rows that
    correspond to the deliveries in `plan` with the edited values:
       - driver / vehicle = the truck assigned in the plan
       - etd / eta        = the snapped times after edits
       - status           = 'cancelled' for cancelled deliveries
    Rows for delivery.status == 'new' are appended after the last data row,
    using the same column order.

    Must use openpyxl (already used by PlanningService) — never pandas to_excel,
    which strips formatting.
    """
```

**Never overwrites the source file.** Output name pattern:
`Weekly Delivery planning W{week}_edited_{YYYYMMDD-HHMM}.xlsx`, written under
`weekly planning/exports/`.

### 4.3 Constraint extraction rules

Read the Excel row verbatim and apply:

| Source column | Becomes | Hard / soft |
|---|---|---|
| `vehicle` non-empty and matches a known truck | `required_truck_id` | hard |
| `driver` non-empty | `required_driver` | soft (warn on mismatch) |
| `delivery_date` | `required_date` | hard (cannot move across days) |
| `etd`, `eta` both present | `time_window=[etd, eta]` | hard |
| `priority` ∈ {urgent, high} | scheduling weight β bump | soft |
| `notes` | shown verbatim in constraints panel | informational |

If a future Excel adds dedicated columns (`required_truck`, `window_start`,
`window_end`, `do_not_split`, `temperature_min`…), wire them through this same
table — no UI change required.

### 4.4 New routes — `backend/app/routes/optimization.py`

```
POST /api/planning/daily/generate
  body: { day: "2026-05-25", source_file?: string }
  → GeneratedPlan

POST /api/planning/daily/export
  body: ExportRequest
  → { download_url, file_name }

GET  /api/planning/daily/download/{file_name}
  → application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

`POST /api/planning/daily/save-draft` (optional, second iteration) writes the
edited plan as a new `PlanVersion` in DB. Defer until skill 05 wiring is in
place.

---

## 5. Frontend changes

### 5.1 New page — `frontend/app/generated-daily-planning/page.jsx`

Structure mirrors `app/daily-planning/page.jsx` for header/stat cards then
swaps the table for the Gantt component. State machine:

```
status: idle → generating → ready → exporting → ready
on Regenerate  → POST /daily/generate, hydrate state
on drag/drop   → mutate React state, mark page dirty
on Add         → open AddDeliveryModal, push into trucks[X].trips or unassigned
on Cancel      → flip delivery.status = 'cancelled' (kept for re-enable)
on Export      → POST /daily/export, then window.location = download_url
```

### 5.2 New components

```
frontend/components/planning/
  GanttBoard.jsx          ← top-level scrollable grid (time × trucks)
  TruckLane.jsx           ← one horizontal row, drop target
  DeliveryBlock.jsx       ← draggable colored block
  DepotMarker.jsx         ← hatched red bar (departure/arrival)
  TimeAxis.jsx            ← sticky top axis 08:00→17:00, 15-min ticks
  ConstraintsPanel.jsx    ← right-rail sticky list, one entry per delivery
  AddDeliveryModal.jsx    ← form: client, qty, window, priority, truck pref
  ExportButton.jsx        ← triggers the POST and download
```

### 5.3 Drag-and-drop library

Use **`@dnd-kit/core`** + **`@dnd-kit/sortable`**. Reasons:
- actively maintained (react-beautiful-dnd is archived);
- works with sensors for touch/pointer/keyboard — accessibility for free;
- no global "DragDropContext at app root" hack — drop-in per page.

Add to `frontend/package.json`:
```
"@dnd-kit/core": "^6.1.0",
"@dnd-kit/modifiers": "^7.0.0",
"@dnd-kit/sortable": "^8.0.0",
```

**Why not native HTML5 DnD?** Lacks snap-to-grid, lacks the
constraint-rejection feedback we need (block bouncing back with a reason).

### 5.4 API client — `frontend/app/services/api.ts`

```ts
export async function generateDailyPlan(day: string) {
  const r = await api.post('/api/planning/daily/generate', { day });
  return r.data as GeneratedPlan;
}

export async function exportDailyPlan(payload: ExportRequest) {
  const r = await api.post('/api/planning/daily/export', payload);
  return r.data as { download_url: string; file_name: string };
}
```

### 5.5 Sidebar entry — `frontend/components/layout/Sidebar.jsx`

Add one entry under `mainNavItems`, immediately after Daily Planning:

```jsx
{ icon: Wand2, label: 'Generated Planning', href: '/generated-daily-planning' },
```

Icon: `Wand2` from `lucide-react` (the "generate" affordance). No other
sidebar items move.

---

## 6. File-by-file checklist

| Layer | File | Action | Status |
|---|---|---|---|
| Backend | `backend/app/services/daily_plan_builder.py` | **new** — orchestrator + greedy fallback | ✅ done |
| Backend | `backend/app/services/excel_exporter.py` | **new** — openpyxl round-trip writer | ✅ done |
| Backend | `backend/app/routes/optimization.py` | edit — add `/daily/generate`, `/daily/export`, `/daily/download/{name}` | ✅ done |
| Backend | `backend/app/services/planning_service.py` | edit — expose `parse_constraints(row)` helper | ✅ done |
| Frontend | `app/generated-daily-planning/page.jsx` | **new** | ✅ done |
| Frontend | `components/planning/GanttBoard.jsx` + siblings (§5.2) | **new** | ✅ done |
| Frontend | `app/services/api.ts` | edit — add 2 functions (§5.4) | ✅ done |
| Frontend | `components/layout/Sidebar.jsx` | edit — 1 line (§5.5) | ✅ done |
| Frontend | `package.json` | edit — 3 deps (§5.3) | ✅ done |
| Skills | `skills/README.md` | edit — add row 14 to the catalog | ✅ done |

---

## 7. Verification

End-to-end smoke test (no DB required — uses xlsx + greedy fallback):

1. Start frontend (`npm run dev`) and backend (`uvicorn app.main:app --reload`).
2. Navigate to `/generated-daily-planning`. The page loads with the current
   day from the existing weekly file and shows a non-empty Gantt within 2s.
3. Drag a block from `Truck 1` to `Truck 3`. The block snaps to the 15-min
   grid. `Truck 1`'s round-trip recomputes its arrival marker.
4. Drag a locked block (one with `required_truck_id`) — it bounces back and a
   toast says "Cofatt #R12 requires Truck 1".
5. Click **+ Add delivery** → fill form → block appears, coloured by client.
6. Right-click a block → **Cancel**. The block grays out; constraint sidebar
   shows it under "Cancelled (1)". Click **Restore** → it returns.
7. Click **Export**. A new file
   `weekly planning/exports/Weekly Delivery planning W0526_edited_*.xlsx`
   appears.
8. Open the exported file: column order matches the source; edited rows have
   new `driver`/`vehicle`/`etd`/`eta`; cancelled rows have `status=cancelled`;
   new rows are appended.
9. Re-open the **source file** and confirm it is byte-identical to its `.bak`
   — i.e. the source is **never** mutated.
10. Refresh `/generated-daily-planning` — the in-progress edits are gone (no
    silent persistence). This is the expected behaviour for v1; persistence
    is the `save-draft` follow-up.

---

## 8. Out of scope for v1

- Multi-day editing (only the selected day is editable).
- Persisting edits across reloads — defer to the `save-draft` route.
- Real-time concurrent editing (two dispatchers on the same day).
- Route map view — already exists at `/map`; we link out to it instead.
- Cost simulation per edit — that's skill 05's "real-time impact" panel and
  should be added to the right rail only after skill 05 is live.

---

## 9. KPI anchor

This page does not introduce new KPI formulas. It is a thin editor on top of
the plan produced by skill 04 and the formulas defined in skill 01. The export
must preserve every column the KPI jobs (skill 08) read; nothing else changes.
