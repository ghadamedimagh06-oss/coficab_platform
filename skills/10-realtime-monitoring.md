# 10 — Real-Time Monitoring & Live Status

> Goal: keep the operations dashboard "alive". Mission statuses, incident counters, and KPI tiles refresh without the planner refreshing the page.

## KPI anchor
- **R4-02 OTD risk** — detect SLA breach risk *before* it becomes a real breach, log a `RETARD_TRAFIC` incident.
- **R4-12** — incoming customer complaints surface immediately, not at month-end.
- **R4** — fleet utilization tile shows real fill rate from active missions.

---

## Architectural decision: polling, not WebSockets (yet)

SWR polling at 30–60s intervals covers 95% of the operational need with zero infrastructure:
- Dashboard KPIs: 60 s
- Live mission map: 15 s
- Incident feed: 30 s
- Dispatch log: 30 s

Add WebSockets in v2 only if drivers acquire mobile devices that emit live GPS. For v1, polling is enough and **dramatically simpler to debug**.

---

## Monitor "agent" — polling loop

`backend/app/agents/monitor.py`:

```python
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.plan import PlanMission, StatutMission
from app.models.demande import DemandeLocal, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.services.incident_service import IncidentService

log = logging.getLogger("monitor")

SLA_TOLERANCE_MIN = 15  # exceeding this triggers an alert

def run():
    db: Session = SessionLocal()
    try:
        in_flight = (db.query(PlanMission)
                       .filter(PlanMission.statut == StatutMission.EN_COURS).all())
        for m in in_flight:
            check_mission(db, m)
        db.commit()
    finally:
        db.close()

def check_mission(db: Session, mission: PlanMission):
    now = datetime.utcnow()
    inc = IncidentService(db)
    for stop in sorted(mission.stops, key=lambda s: s.ordre_livraison):
        d = stop.demande
        if d.statut in (StatutDemande.LIVREE, StatutDemande.ANNULEE):
            continue
        # If the planned ETA is in the past and demande not delivered, slipping
        if stop.eta_prevue and stop.eta_prevue + timedelta(minutes=SLA_TOLERANCE_MIN) < now:
            if not already_flagged(db, stop.id):
                inc.log(
                    type=EvenementType.RETARD_TRAFIC,
                    description=f"ETA missed by {int((now - stop.eta_prevue).total_seconds()//60)} min — stop #{stop.ordre_livraison}",
                    mission_id=mission.id,
                    demande_id=d.id,
                    impact_delai_min=int((now - stop.eta_prevue).total_seconds() // 60),
                )
                log.warning("[monitor] auto-incident mission=%s stop=%s", mission.id, stop.id)
            break  # one alert per mission per pass is enough

def already_flagged(db: Session, stop_id: int) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    return db.query(EvenementAlea).filter(
        EvenementAlea.type == EvenementType.RETARD_TRAFIC,
        EvenementAlea.date_evenement > cutoff,
        EvenementAlea.mission_id.isnot(None),
    ).count() > 0
```

Schedule it every 30 seconds (skill 08's scheduler block already has the line).

---

## Live endpoints

```
GET /api/tracking/live                 active missions + ETAs + load %
GET /api/tracking/missions/{id}/status detail (stops, current stop, slip in minutes)
POST /api/tracking/missions/{id}/checkin  driver app endpoint (v2 — GPS)
POST /api/tracking/stops/{id}/delivered   { quantite_livree_kg } — close-out a stop
```

The "live" endpoint returns the shape the existing map page expects (`frontend/components/map/TruckMap.tsx`). Don't restructure it.

---

## Mission close-out (operator-driven for v1)

The transport manager (or eventually the driver via mobile) marks each stop delivered. Endpoint logic:

```python
@router.post("/stops/{stop_id}/delivered")
def deliver(stop_id: int, payload: DeliveredIn, db: Session = Depends(get_db)):
    stop = db.get(MissionDemande, stop_id)
    demande = stop.demande
    demande.quantite_livree_kg = payload.quantite_livree_kg
    demande.heure_arrivee_reelle = datetime.utcnow()
    demande.statut = StatutDemande.LIVREE
    demande.livree_a_temps = (demande.heure_arrivee_reelle <= (stop.eta_prevue + timedelta(minutes=SLA_TOLERANCE_MIN)))
    stop.statut = StatutDemande.LIVREE
    stop.eta_reelle = demande.heure_arrivee_reelle
    db.commit()
    # No synchronous KPI recompute — the nightly job handles it (skill 08).
    return {"ok": True, "on_time": demande.livree_a_temps}
```

This is what feeds R4-02 OTD and R4-06 OTIF.

When the **last** stop of a mission is delivered:

```python
@event.listens_for(MissionDemande, "after_update")
def _maybe_close_mission(_, __, target):
    # If all stops of the mission are LIVREE or ANNULEE, close the mission.
    # Implementation: count, compare, flip statut.
    pass
```

Set `mission.statut = TERMINEE`, `heure_retour_reelle = now`, compute `km_parcourus`, `fuel_consomme_l` (from baseline × km — or skip if not tracked).

---

## Frontend: live updates

Already covered by SWR's `refreshInterval`. Specific tunings:

```typescript
// Dashboard KPIs
useSWR('/api/metrics/kpi', fetcher, { refreshInterval: 60_000 });

// Map live missions
useSWR('/api/tracking/live', fetcher, { refreshInterval: 15_000 });

// Incident feed
useSWR('/api/incidents?resolu=false&limit=10', fetcher, { refreshInterval: 30_000 });

// Mission detail
useSWR(`/api/tracking/missions/${id}/status`, fetcher, { refreshInterval: 10_000 });
```

SWR also refetches on window focus by default — that's the right behavior for a planner returning to the tab.

---

## Optional: Server-Sent Events for incident pop-ups

If polling every 30s feels slow for incidents, add one SSE endpoint:

```
GET /api/events/stream            text/event-stream
```

Frontend opens an `EventSource`, server pushes `{ type: "incident", id: ... }` and the incident hook revalidates. **Optional for v1**; polling works.

---

## Anti-patterns

- ❌ Recomputing KPIs on every poll. Polls read pre-aggregated rows; the nightly job aggregates.
- ❌ Re-rendering the entire dashboard tree on each poll. SWR's `keepPreviousData: true` prevents flicker — set it on every hook.
- ❌ Using a global event bus. SWR cache invalidation is enough.
- ❌ WebSockets for v1. Maintenance burden too high for the operational value.

---

## Verification

1. Create a mission with one stop, `eta_prevue` set 5 min ago, mission `statut='EN_COURS'`, demande not delivered.
2. Wait 30 s. Monitor job fires → `evenement_alea` row appears, `type='RETARD_TRAFIC'`, `impact_delai_min ≈ 5`.
3. Dashboard incident card auto-updates within 30 s (no refresh).
4. Mark the stop delivered via API. Demande `statut='LIVREE'`, `livree_a_temps=false`.
5. Run nightly KPI job → R4-02 dropped accordingly.
