from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any
import json
import math
import os
from datetime import datetime, timedelta, timezone

from app.database import get_db, get_db_optional
from app.agents.monitor import SLA_TOLERANCE_MIN
from app.models.demande import StatutDemande
from app.models.plan import MissionDemande, PlanMission, StatutMission
from app.models.transport_tracking import TransportTracking
from app.models.client import Client
from app.services.auth_service import get_current_user, require_role

router = APIRouter()


class DeliveredIn(BaseModel):
    quantite_livree_kg: float = Field(..., ge=0)


class SimulationIn(BaseModel):
    mission_id: int
    progress_pct: float = Field(default=50, ge=0, le=100)
    delay_minutes: int = Field(default=0, ge=0, le=1440)


@router.get("/live")
async def get_live_tracking(
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_optional),
):
    """Return recent tracking records (last 100)."""
    if not db:
        return {"tracking_data": [], "count": 0, "source": "offline", "clients": []}
    records = _tracking_records(db)
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
            "source": r.source,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        })
    active_missions = _active_missions(db)
    simulatable_missions = [
        mission for mission in active_missions
        if mission["status"] == StatutMission.EN_COURS.value
    ]
    return {
        "tracking_data": result,
        "count": len(result),
        "active_missions": active_missions,
        "simulatable_missions": simulatable_missions,
        "mission_count": len(active_missions),
        "clients": _client_markers(db),
        "source": "database",
    }


@router.get("/status")
async def get_tracking_status(
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_optional),
):
    """Compatibility endpoint for Agent 4 tracking polling."""
    return await get_live_tracking(_user, db)


@router.get("/map-data")
async def get_map_data(
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_optional),
):
    """Return the map-ready tracking/client payload from application data."""
    payload = await get_live_tracking(_user, db)
    return {
        **payload,
        "source": payload.get("source", "database"),
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

    now = datetime.now(timezone.utc)
    demande = stop.demande
    on_time = None
    if stop.eta_prevue is not None:
        on_time = now <= _as_utc(stop.eta_prevue) + timedelta(minutes=SLA_TOLERANCE_MIN)

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
async def sync_tracking(
    payload: Dict[str, Any],
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db_optional),
    x_tfm_key: str | None = Header(None, alias="X-TFM-Key"),
):
    """Persist tracking sync payload into transport_tracking table.

    Expected payload: {"items": [{transport object}, ...], "source": "agent"}
    Returns: count of items stored.
    """
    items = payload.get("items") or []
    requested_source = str(payload.get("source") or "MANUAL").upper()
    if requested_source == "MAP_SIMULATION":
        raise HTTPException(status_code=422, detail="use /simulation/run for map simulation samples")
    if requested_source == "TFM":
        expected_key = os.getenv("TFM_INGEST_API_KEY")
        if not expected_key:
            raise HTTPException(status_code=503, detail="TFM ingestion is not configured")
        if x_tfm_key != expected_key:
            raise HTTPException(status_code=401, detail="invalid TFM ingestion key")
        source = "TFM"
    else:
        source = "MANUAL"
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Invalid payload: 'items' must be a list")
    if not db:
        return {
            "status": "skipped",
            "count": 0,
            "persisted": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    stored = 0
    alerts_created = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail=f"items[{index}] must be an object")
        transport_id = str(item.get("id") or item.get("transport_id") or "").strip()
        if not transport_id:
            raise HTTPException(status_code=422, detail=f"items[{index}] requires transport_id")
        if len(transport_id) > 100:
            raise HTTPException(status_code=422, detail=f"items[{index}].transport_id exceeds 100 characters")
        status_value = item.get("status")
        if status_value is not None and len(str(status_value)) > 50:
            raise HTTPException(status_code=422, detail=f"items[{index}].status exceeds 50 characters")
        location = item.get("location")
        if location is not None and not isinstance(location, dict):
            raise HTTPException(status_code=422, detail=f"items[{index}].location must be an object")
        if location is not None:
            try:
                latitude = float(location["lat"])
                longitude = float(location["lng"])
            except (KeyError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"items[{index}].location requires numeric lat/lng") from exc
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise HTTPException(status_code=422, detail=f"items[{index}].location is outside valid ranges")
            location = {**location, "lat": latitude, "lng": longitude}
        try:
            eta_raw = item.get("eta_hours", item.get("eta"))
            distance_raw = item.get(
                "distance_remaining",
                item.get("distance", item.get("distance_km")),
            )
            eta = float(eta_raw) if eta_raw is not None else None
            distance_remaining = float(distance_raw) if distance_raw is not None else None
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"items[{index}] has invalid numeric data") from exc
        if eta is not None and (not math.isfinite(eta) or eta < 0):
            raise HTTPException(status_code=422, detail=f"items[{index}].eta must be a finite non-negative number")
        if distance_remaining is not None and (
            not math.isfinite(distance_remaining) or distance_remaining < 0
        ):
            raise HTTPException(status_code=422, detail=f"items[{index}].distance must be a finite non-negative number")

        record = TransportTracking(
            transport_id=transport_id,
            status=status_value,
            location=json.dumps(location) if location is not None else None,
            eta_hours=eta,
            distance_remaining=distance_remaining,
            source=source,
        )
        db.add(record)
        db.flush()
        stored += 1
        mission_id = item.get("mission_id")
        if mission_id is None and transport_id.startswith("mission-"):
            mission_id = transport_id.removeprefix("mission-")
        delay_minutes = item.get("delay_minutes", item.get("slip_minutes"))
        if mission_id is not None and delay_minutes is not None:
            try:
                mission_id = int(mission_id)
                delay_minutes = int(delay_minutes)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"items[{index}] has invalid delay data") from exc
            if delay_minutes < 0 or delay_minutes > 1440:
                raise HTTPException(status_code=422, detail=f"items[{index}].delay_minutes is outside 0..1440")
            alerts_created += _create_tracking_delay_incident(
                db,
                mission_id,
                delay_minutes,
                source,
            )

    db.commit()
    return {
        "status": "synced",
        "count": stored,
        "alerts_created": alerts_created,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/simulation/run")
async def run_map_simulation(
    payload: SimulationIn,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    from app.services.tracking_simulation_service import TrackingSimulationService

    try:
        return TrackingSimulationService(db).run(
            payload.mission_id,
            progress_pct=payload.progress_pct,
            delay_minutes=payload.delay_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tfm/sync")
async def sync_tfm_tracking(
    payload: Dict[str, Any],
    db: Session = Depends(get_db_optional),
    x_tfm_key: str | None = Header(None, alias="X-TFM-Key"),
):
    """Machine-authenticated TFM ingestion; no user JWT is required."""
    tfm_payload = {**payload, "source": "TFM"}
    return await sync_tracking(
        tfm_payload,
        {"username": "tfm-service", "role": "service"},
        db,
        x_tfm_key,
    )


def _active_missions(db: Session) -> list[dict[str, Any]]:
    missions = (
        db.query(PlanMission)
        .filter(PlanMission.statut.in_([StatutMission.PLANIFIEE, StatutMission.EN_COURS]))
        .order_by(PlanMission.date_mission.desc(), PlanMission.id.desc())
        .limit(50)
        .all()
    )
    return [_mission_summary(mission) for mission in missions]


def _create_tracking_delay_incident(
    db: Session,
    mission_id: int,
    delay_minutes: int,
    source: str,
) -> int:
    """Turn a numeric TFM/map slip into one deduplicated incident."""
    from app.agents.monitor import SLA_TOLERANCE_MIN, already_flagged
    from app.models.evenement import EvenementType
    from app.services.incident_service import IncidentService

    if delay_minutes <= SLA_TOLERANCE_MIN:
        return 0
    mission = db.get(PlanMission, mission_id)
    if mission is None or mission.statut not in {StatutMission.PLANIFIEE, StatutMission.EN_COURS}:
        return 0
    closed = {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}
    stop = next(
        (
            candidate
            for candidate in sorted(
                mission.mission_demandes,
                key=lambda item: (item.ordre_livraison, item.id),
            )
            if _status_value(candidate.statut) not in closed
        ),
        None,
    )
    if stop is None or already_flagged(db, mission_id, stop.demande_id):
        return 0
    IncidentService(db).log(
        type=EvenementType.RETARD_TRAFIC,
        description=(
            f"{source} tracking: mission {mission_id} is delayed by "
            f"{delay_minutes} minutes"
        ),
        mission_id=mission_id,
        demande_id=stop.demande_id,
        impact_delai_min=delay_minutes,
        cause=source,
        commit=False,
    )
    return 1


def _tracking_records(db: Session) -> list[TransportTracking]:
    # The live map needs current state, not raw history. Keep only the newest
    # sample for each transport; historical samples remain stored in the table.
    latest_ids = (
        db.query(func.max(TransportTracking.id).label("id"))
        .group_by(TransportTracking.transport_id)
        .subquery()
    )
    return (
        db.query(TransportTracking)
        .join(latest_ids, TransportTracking.id == latest_ids.c.id)
        .order_by(TransportTracking.id.desc())
        .limit(100)
        .all()
    )


def _client_markers(db: Session) -> list[dict[str, Any]]:
    clients = (
        db.query(Client)
        .filter(Client.latitude.isnot(None), Client.longitude.isnot(None))
        .order_by(Client.nom)
        .limit(200)
        .all()
    )
    return [
        {
            "id": client.id,
            "customer": client.nom,
            "destination": client.city or client.address or client.nom,
            "lat": float(client.latitude),
            "lng": float(client.longitude),
            "latitude": float(client.latitude),
            "longitude": float(client.longitude),
        }
        for client in clients
    ]


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
    actual = stop.eta_reelle or datetime.now(timezone.utc)
    slip = int((_as_utc(actual) - _as_utc(stop.eta_prevue)).total_seconds() // 60)
    return max(0, slip)


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _as_utc(dt: datetime) -> datetime:
    """Make a datetime UTC-aware. DB columns are DateTime(timezone=True) but
    SQLite returns them naive, so coerce before comparing to an aware now()."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
