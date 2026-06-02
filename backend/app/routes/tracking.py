from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
from datetime import datetime, timedelta

from app.database import get_db, get_db_optional
from app.agents.monitor import SLA_TOLERANCE_MIN
from app.models.demande import StatutDemande
from app.models.plan import MissionDemande, PlanMission, StatutMission
from app.models.transport_tracking import TransportTracking
from app.services.auth_service import require_role

router = APIRouter()


class DeliveredIn(BaseModel):
    quantite_livree_kg: float = Field(..., ge=0)


@router.get("/live")
async def get_live_tracking(db: Session = Depends(get_db_optional)):
    """Return recent tracking records (last 100)."""
    if not db:
        return {"tracking_data": [], "count": 0, "source": "offline"}
    records = db.query(TransportTracking).order_by(TransportTracking.id.desc()).limit(100).all()
    result = []
    for r in records:
        try:
            location = json.loads(r.location) if r.location else None
        except Exception:
            location = None
        result.append({
            "transport_id": r.transport_id,
            "status": r.status,
            "location": location,
            "eta_hours": r.eta_hours,
            "distance_remaining": r.distance_remaining,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        })
    active_missions = _active_missions(db)
    return {
        "tracking_data": result,
        "count": len(result),
        "active_missions": active_missions,
        "mission_count": len(active_missions),
    }


@router.get("/missions/{mission_id}/status")
async def get_mission_status(mission_id: int, db: Session = Depends(get_db)):
    mission = db.get(PlanMission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return _mission_status(mission)


@router.post("/stops/{stop_id}/delivered")
async def mark_stop_delivered(
    stop_id: int,
    payload: DeliveredIn,
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    stop = db.get(MissionDemande, stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail="stop not found")
    if _status_value(stop.statut) == StatutDemande.ANNULEE.value:
        raise HTTPException(status_code=400, detail="cancelled stops cannot be delivered")
    if stop.demande is None:
        raise HTTPException(status_code=400, detail="stop has no linked demande")

    now = datetime.utcnow()
    demande = stop.demande
    on_time = None
    if stop.eta_prevue is not None:
        on_time = now <= stop.eta_prevue + timedelta(minutes=SLA_TOLERANCE_MIN)

    demande.quantite_livree_kg = payload.quantite_livree_kg
    demande.heure_arrivee_reelle = now
    demande.statut = StatutDemande.LIVREE
    demande.livree_a_temps = on_time
    stop.statut = StatutDemande.LIVREE.value
    stop.eta_reelle = now

    mission = stop.mission
    if mission is not None:
        if _all_stops_closed(mission):
            mission.statut = StatutMission.TERMINEE
            mission.heure_retour_reelle = now
        elif mission.statut == StatutMission.PLANIFIEE:
            mission.statut = StatutMission.EN_COURS

    db.commit()
    db.refresh(stop)
    if mission is not None:
        db.refresh(mission)

    return {
        "ok": True,
        "stop_id": stop.id,
        "demande_id": stop.demande_id,
        "on_time": on_time,
        "mission_status": _status_value(mission.statut) if mission is not None else None,
        "delivered_at": stop.eta_reelle.isoformat() if stop.eta_reelle else None,
    }


@router.post("/sync")
async def sync_tracking(payload: Dict[str, Any], db: Session = Depends(get_db_optional)):
    """Persist tracking sync payload into transport_tracking table.

    Expected payload: {"items": [{transport object}, ...], "source": "agent"}
    Returns: count of items stored.
    """
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Invalid payload: 'items' must be a list")
    if not db:
        return {
            "status": "skipped",
            "count": 0,
            "persisted": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

    stored = 0
    for item in items:
        try:
            transport_id = str(item.get("id") or item.get("transport_id") or "")
            status = item.get("status")
            location = item.get("location")
            eta = item.get("eta_hours") or item.get("eta")
            distance_remaining = item.get("distance_remaining") or item.get("distance") or item.get("distance_km")

            record = TransportTracking(
                transport_id=transport_id,
                status=status,
                location=json.dumps(location) if location is not None else None,
                eta_hours=float(eta) if eta is not None else None,
                distance_remaining=float(distance_remaining) if distance_remaining is not None else None,
                source=payload.get("source")
            )
            db.add(record)
            stored += 1
        except Exception:
            continue

    db.commit()
    return {"status": "synced", "count": stored, "timestamp": datetime.utcnow().isoformat()}


def _active_missions(db: Session) -> list[dict[str, Any]]:
    missions = (
        db.query(PlanMission)
        .filter(PlanMission.statut.in_([StatutMission.PLANIFIEE, StatutMission.EN_COURS]))
        .order_by(PlanMission.date_mission.desc(), PlanMission.id.desc())
        .limit(50)
        .all()
    )
    return [_mission_summary(mission) for mission in missions]


def _mission_status(mission: PlanMission) -> dict[str, Any]:
    stops = sorted(mission.mission_demandes, key=lambda stop: (stop.ordre_livraison, stop.id))
    stop_payloads = [_stop_payload(stop) for stop in stops]
    current = next(
        (
            stop for stop in stop_payloads
            if stop["statut"] not in {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}
        ),
        None,
    )
    return {
        **_mission_summary(mission),
        "current_stop_id": current["id"] if current else None,
        "stops": stop_payloads,
    }


def _mission_summary(mission: PlanMission) -> dict[str, Any]:
    stops = list(mission.mission_demandes)
    delivered = sum(
        1 for stop in stops
        if _status_value(stop.statut) == StatutDemande.LIVREE.value
    )
    return {
        "id": mission.id,
        "status": _status_value(mission.statut),
        "date_mission": mission.date_mission.isoformat() if mission.date_mission else None,
        "chauffeur_id": mission.chauffeur_id,
        "camion_id": mission.camion_id,
        "load_eff_pct": float(mission.load_eff_pct) if mission.load_eff_pct is not None else None,
        "stop_count": len(stops),
        "delivered_count": delivered,
        "next_eta": _next_eta(stops),
        "slip_minutes": _mission_slip_minutes(stops),
    }


def _stop_payload(stop: MissionDemande) -> dict[str, Any]:
    demande = stop.demande
    return {
        "id": stop.id,
        "demande_id": stop.demande_id,
        "ordre_livraison": stop.ordre_livraison,
        "statut": _status_value(stop.statut),
        "eta_prevue": stop.eta_prevue.isoformat() if stop.eta_prevue else None,
        "eta_reelle": stop.eta_reelle.isoformat() if stop.eta_reelle else None,
        "slip_minutes": _stop_slip_minutes(stop),
        "client_id": demande.client_id if demande else None,
        "quantite_kg": float(demande.quantite_kg) if demande and demande.quantite_kg is not None else None,
        "quantite_livree_kg": (
            float(demande.quantite_livree_kg)
            if demande and demande.quantite_livree_kg is not None
            else None
        ),
        "livree_a_temps": demande.livree_a_temps if demande else None,
    }


def _all_stops_closed(mission: PlanMission) -> bool:
    closed = {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}
    return all(_status_value(stop.statut) in closed for stop in mission.mission_demandes)


def _next_eta(stops: list[MissionDemande]) -> str | None:
    pending = [
        stop.eta_prevue for stop in stops
        if _status_value(stop.statut) not in {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}
        and stop.eta_prevue is not None
    ]
    if not pending:
        return None
    return min(pending).isoformat()


def _mission_slip_minutes(stops: list[MissionDemande]) -> int:
    return max((_stop_slip_minutes(stop) for stop in stops), default=0)


def _stop_slip_minutes(stop: MissionDemande) -> int:
    if not stop.eta_prevue:
        return 0
    actual = stop.eta_reelle or datetime.utcnow()
    slip = int((actual - stop.eta_prevue).total_seconds() // 60)
    return max(0, slip)


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
