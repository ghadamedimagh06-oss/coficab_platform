from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evenement import EvenementAlea, EvenementType
from app.services.auth_service import get_current_user, require_role
from app.services.incident_service import IncidentService

router = APIRouter()


class IncidentCreate(BaseModel):
    type: EvenementType
    description: Optional[str] = None
    mission_id: Optional[int] = None
    demande_id: Optional[int] = None
    impact_delai_min: int = Field(default=0, ge=0)
    cause: Optional[str] = None


class IncidentResolve(BaseModel):
    note: Optional[str] = None


def _incident_dict(incident: EvenementAlea) -> dict:
    incident_type = incident.type.value if hasattr(incident.type, "value") else incident.type
    return {
        "id": incident.id,
        "plan_version_id": incident.plan_version_id,
        "mission_id": incident.mission_id,
        "demande_id": incident.demande_id,
        "type": incident_type,
        "description": incident.description,
        "impact_delai_min": incident.impact_delai_min or 0,
        "resolu": bool(incident.resolu),
        "date_evenement": incident.date_evenement.isoformat() if incident.date_evenement else None,
        "date_resolution": incident.date_resolution.isoformat() if incident.date_resolution else None,
        "cause": incident.cause,
    }


@router.post("")
def create_incident(
    payload: IncidentCreate,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    try:
        incident = service.log(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _incident_dict(incident)


@router.post("/{incident_id}/resolve")
def resolve_incident(
    incident_id: int,
    payload: IncidentResolve,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    try:
        incident = service.resolve(incident_id, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _incident_dict(incident)


@router.get("/stats")
def incident_stats(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month_num = (int(part) for part in month.split("-", 1))
    start = datetime(year, month_num, 1)
    end = datetime(year + 1, 1, 1) if month_num == 12 else datetime(year, month_num + 1, 1)

    rows = (
        db.query(
            EvenementAlea.type,
            func.count(EvenementAlea.id),
            func.coalesce(func.sum(EvenementAlea.impact_delai_min), 0),
        )
        .filter(EvenementAlea.date_evenement >= start, EvenementAlea.date_evenement < end)
        .group_by(EvenementAlea.type)
        .all()
    )
    counts = {
        (incident_type.value if hasattr(incident_type, "value") else incident_type): {
            "count": int(count),
            "impact_delai_min": int(delay or 0),
        }
        for incident_type, count, delay in rows
    }
    return {"month": month, "by_type": counts}


@router.get("")
def list_incidents(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    type: Optional[EvenementType] = Query(None),
    resolu: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(EvenementAlea)
    if from_date is not None:
        query = query.filter(EvenementAlea.date_evenement >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        query = query.filter(EvenementAlea.date_evenement <= datetime.combine(to_date, datetime.max.time()))
    if type is not None:
        query = query.filter(EvenementAlea.type == type)
    if resolu is not None:
        query = query.filter(EvenementAlea.resolu == resolu)

    total = query.count()
    incidents = (
        query.order_by(EvenementAlea.date_evenement.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"incidents": [_incident_dict(incident) for incident in incidents], "total": total}


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = db.get(EvenementAlea, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return _incident_dict(incident)
