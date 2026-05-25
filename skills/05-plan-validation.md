# 05 — Plan Validation (Human-in-the-Loop)

> Goal: let the transport manager review the DRAFT plan in the Gantt UI, drag/reassign as needed, see the KPI impact of every change in real time, then **lock** the plan with one click. After lock, dispatch fires (skill 06).

## KPI anchor
- **R4-02 OTD / R4-06 OTIF** — every manual reassignment recomputes expected delay.
- **R4 Load Efficiency** — every reassignment recomputes truck fill rate.
- **R4-02-PF Premium Freight** — adding a last-minute stop may flip mode to `PREMIUM`; cost surfaced immediately.
- **Audit trail (governance)** — every change is recorded in `planning_change_log`. Required by spec §5.6.

---

## Lifecycle

```
DRAFT (optimizer output)
  → EN_REVUE (planner is editing)
    → VALIDE (locked, dispatch fires)
      → EXECUTE (drivers rolling)
        → CLOTURE (close-out, KPIs aggregated)
```

Transitions:
- `DRAFT → EN_REVUE` — opening the plan in the planning UI.
- `EN_REVUE → VALIDE` — "Valider" button; locks the version.
- Any edit after `VALIDE` → creates a new `plan_version` with `version_number + 1`, status `DRAFT`. **Never mutate a validated row.**

---

## Service: `backend/app/services/planning_service.py`

```python
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.plan import PlanVersion, PlanMission, MissionDemande, StatutPlan
from app.models.demande import DemandeLocal, StatutDemande
from app.services.kpi_service import KpiService

class PlanningService:
    def __init__(self, db: Session):
        self.db = db
        self.kpi = KpiService(db)

    # ----- impact preview (used by drag-and-drop) -------------------
    def preview_impact(self, plan_version_id: int) -> dict:
        version = self.db.get(PlanVersion, plan_version_id)
        missions = version.missions

        total_km = sum((m.km_parcourus or 0) for m in missions)
        total_kg = sum((m.charge_kg or 0) for m in missions)
        load_eff = (
            sum((m.load_eff_pct or 0) for m in missions) / len(missions)
            if missions else 0
        )
        premium_count = sum(1 for m in missions if m.mode == "PREMIUM")
        premium_cost  = sum((m.cout_premium_eur or 0) for m in missions)
        expected_otd  = self._expected_otd(missions)
        expected_fuel = self._expected_fuel_eff(missions)

        return {
            "plan_version_id": plan_version_id,
            "total_km": round(total_km, 1),
            "total_kg": round(total_kg, 1),
            "load_efficiency_pct": round(load_eff, 2),
            "expected_otd_pct": round(expected_otd, 2),
            "expected_fuel_ml_per_tkm": round(expected_fuel, 3),
            "premium_freight_count": premium_count,
            "premium_freight_eur": round(premium_cost, 2),
            # Color bands are read from kpi_definition so the UI matches the dashboard
            "colors": {
                "otd": self._color("R4-02", expected_otd),
                "fuel": self._color("R4-13", expected_fuel),
                "load": self._color("R4",   load_eff),
                "premium_eur": self._color("R4-02-PF", premium_cost),
            }
        }

    def _color(self, code, value):
        from app.models.kpi import KpiDefinition
        d = self.db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
        return self.kpi.color_for(d, value) if d else "grey"

    def _expected_otd(self, missions) -> float:
        # Naive: % of stops whose ETA falls inside the demande window.
        on_time = 0; total = 0
        for m in missions:
            for md in m.stops:
                total += 1
                d = md.demande
                if d.heure_arrivee_prevue and md.eta_prevue and md.eta_prevue <= d.heure_arrivee_prevue:
                    on_time += 1
        return (on_time / total * 100) if total else 0.0

    def _expected_fuel_eff(self, missions) -> float:
        litres  = sum((m.km_parcourus or 0) * 0.30 for m in missions)   # 30L/100km baseline
        tonnage = sum((m.charge_kg or 0) for m in missions)
        km      = sum((m.km_parcourus or 0) for m in missions)
        if tonnage == 0 or km == 0: return 0.0
        return litres * 1000 / (tonnage / 1000 * km)

    # ----- modifications (during EN_REVUE) --------------------------
    def reassign_demande(self, demande_id: int, target_mission_id: int, user_id: int, reason: str):
        md = self.db.query(MissionDemande).filter(MissionDemande.demande_id == demande_id).first()
        if md is None: raise ValueError("demande not in any mission")
        plan = md.mission.plan_version
        if plan.statut_plan == StatutPlan.VALIDE:
            raise ValueError("plan validated — create a new version instead")
        self._log_change(plan.id, "mission_id", str(md.mission_id), str(target_mission_id), reason, user_id)
        md.mission_id = target_mission_id
        # re-number ordre_livraison within the target mission
        self._renumber(target_mission_id)
        self.db.commit()

    def _renumber(self, mission_id: int):
        stops = (self.db.query(MissionDemande)
                        .filter(MissionDemande.mission_id == mission_id)
                        .order_by(MissionDemande.ordre_livraison)
                        .all())
        for i, s in enumerate(stops, start=1):
            s.ordre_livraison = i

    def _log_change(self, plan_version_id, field, old, new, reason, user_id):
        from app.models.audit import PlanningChangeLog
        self.db.add(PlanningChangeLog(
            plan_version_id=plan_version_id,
            field_changed=field, old_value=old, new_value=new,
            reason_category="manual_edit", reason_text=reason,
            user_id=user_id,
        ))

    # ----- validate (lock) ------------------------------------------
    def validate(self, plan_version_id: int, user: str) -> PlanVersion:
        v = self.db.get(PlanVersion, plan_version_id)
        if v.statut_plan == StatutPlan.VALIDE:
            return v
        v.statut_plan = StatutPlan.VALIDE
        v.date_validation = datetime.utcnow()
        v.valide_par = user
        self.db.commit()
        # Trigger dispatch (skill 06)
        from app.services.dispatch_service import DispatchService
        DispatchService(self.db).dispatch_plan(v)
        return v
```

---

## API endpoints

```
GET  /api/planning/{plan_version_id}             full plan (missions + stops)
GET  /api/planning/{plan_version_id}/impact      KPI preview JSON (called on every drag)
POST /api/planning/{plan_version_id}/reassign    { demande_id, target_mission_id, reason }
POST /api/planning/{plan_version_id}/validate    locks → triggers dispatch
POST /api/planning/{plan_version_id}/clone       creates a new DRAFT version from a validated one
GET  /api/planning/{plan_version_id}/changelog   audit trail
```

The impact endpoint must respond in **< 200 ms** — the UI calls it on every drag-end event. The `preview_impact` implementation above is O(N) over missions and stops, so it scales to ~500 stops without issue.

---

## Frontend wiring (UI unchanged)

Page: `frontend/app/planning/page.jsx` (the Gantt) and `frontend/app/daily-planning/page.jsx`. They already render mock missions. Change:

```jsx
// BEFORE (mock)
import { planningData } from '@/data/planningData';

// AFTER
import useSWR from 'swr';
import { fetcher } from '@/lib/api';

const { data: plan } = useSWR(`/api/planning/${planVersionId}`, fetcher);
const { data: impact, mutate: refreshImpact } = useSWR(
  `/api/planning/${planVersionId}/impact`, fetcher
);

// onDragEnd:
await fetch(`/api/planning/${planVersionId}/reassign`, {
  method: 'POST',
  body: JSON.stringify({ demande_id, target_mission_id, reason: 'manual' }),
});
refreshImpact();   // KPI cards re-render with new values + new colors
```

The **KPI impact panel** on the planning page (today's mock) reads from `impact`. Same JSX, same colors, just bound to the API.

---

## Audit trail UI

Use `frontend/components/JustificationModal.jsx` (already exists) for the reason prompt before applying a destructive change. The modal output goes into the `reason` field of the reassign payload.

---

## Anti-patterns

- ❌ Modifying a validated plan in place — always clone first.
- ❌ Recomputing KPI colors in the frontend — use `impact.colors` from the API.
- ❌ Logging changes only for the final validation — log **every** drag/edit so the audit trail is honest.
- ❌ Dispatching before validation — the validate endpoint is the only path to dispatch.

---

## Verification

1. Generate a DRAFT plan with the optimizer (skill 04).
2. Open `/planning?id=<plan_version_id>` — Gantt renders.
3. Drag one demande from mission A to mission B. Network panel: one POST `/reassign`, one GET `/impact`.
4. KPI cards update: load eff, OTD %, fuel mL/T.km all change. Colors match the dashboard scheme.
5. Click "Valider". The plan_version row flips to `statut_plan='VALIDE'`. Dispatch service log shows "notifying 2 drivers".
6. Try editing again → API returns 409, UI offers "Clone this plan as new version".
7. `SELECT * FROM planning_change_log WHERE plan_version_id = <id>` shows one row per drag, plus the validation event.
