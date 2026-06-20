"""
Execution & ePOD endpoints — docs/TMS_ROADMAP.md §4/§5.

The operational loop on top of a persisted plan:
  POST /api/execution/plans/{id}/validate     DRAFT/EN_REVUE -> VALIDE
  POST /api/execution/plans/{id}/start         -> EXECUTE, all missions EN_COURS
  POST /api/execution/missions/{id}/start      one mission -> EN_COURS
  POST /api/execution/stops/{id}/confirm        ePOD: stop -> LIVREE (+ proof)
  POST /api/execution/stops/{id}/exception      delivery exception -> ANNULEE
  GET  /api/execution/plans/{id}/status         live progress
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import require_auth, require_role
from app.services.execution_service import ExecutionError, ExecutionService

router = APIRouter()


class ConfirmDeliveryRequest(BaseModel):
    quantite_livree_kg: Optional[float] = Field(default=None, ge=0)
    delivered_at: Optional[datetime] = None
    on_time: Optional[bool] = None
    signataire: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None


class ExceptionRequest(BaseModel):
    type: str = Field(..., description="EvenementType, e.g. CLIENT_INDISPONIBLE")
    description: Optional[str] = None
    cancel: bool = True


def _svc(db: Session) -> ExecutionService:
    return ExecutionService(db)


def _handle(fn):
    try:
        return fn()
    except ExecutionError as exc:
        msg = str(exc)
        raise HTTPException(status_code=404 if "not found" in msg else 409, detail=msg)


@router.post("/plans/{plan_version_id}/validate")
def validate_plan(
    plan_version_id: int,
    user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    plan = _handle(lambda: _svc(db).validate_plan(plan_version_id, user.get("username", "unknown")))
    return {"plan_version_id": plan.id, "statut_plan": str(plan.statut_plan), "valide_par": plan.valide_par}


@router.post("/plans/{plan_version_id}/start")
def start_plan(
    plan_version_id: int,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    plan = _handle(lambda: _svc(db).start_plan(plan_version_id))
    return _svc(db).plan_status(plan.id)


@router.post("/missions/{mission_id}/start")
def start_mission(
    mission_id: int,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    mission = _handle(lambda: _svc(db).start_mission(mission_id))
    return {"mission_id": mission.id, "statut": str(mission.statut), "heure_sortie_reelle": mission.heure_sortie_reelle}


@router.post("/stops/{mission_demande_id}/confirm")
def confirm_delivery(
    mission_demande_id: int,
    payload: ConfirmDeliveryRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    proof = _handle(lambda: _svc(db).confirm_delivery(
        mission_demande_id,
        quantite_livree_kg=payload.quantite_livree_kg,
        delivered_at=payload.delivered_at,
        on_time=payload.on_time,
        signataire=payload.signataire,
        photo_url=payload.photo_url,
        notes=payload.notes,
        created_by=user.get("username"),
    ))
    return {
        "proof_id": proof.id,
        "mission_demande_id": proof.mission_demande_id,
        "demande_id": proof.demande_id,
        "statut": str(proof.statut),
        "delivered_at": proof.delivered_at,
        "quantite_livree_kg": float(proof.quantite_livree_kg) if proof.quantite_livree_kg is not None else None,
        "on_time": proof.on_time,
    }


@router.post("/stops/{mission_demande_id}/exception")
def report_exception(
    mission_demande_id: int,
    payload: ExceptionRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    ev = _handle(lambda: _svc(db).report_exception(
        mission_demande_id,
        type=payload.type,
        description=payload.description,
        cancel=payload.cancel,
        created_by=user.get("username"),
    ))
    return {"event_id": ev.id, "type": str(ev.type), "demande_id": ev.demande_id, "cancelled": payload.cancel}


@router.get("/plans/{plan_version_id}/status")
def plan_status(
    plan_version_id: int,
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return _handle(lambda: _svc(db).plan_status(plan_version_id))
