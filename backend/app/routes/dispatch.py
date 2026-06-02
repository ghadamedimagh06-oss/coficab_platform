from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import NotificationLog
from app.models.plan import PlanMission, PlanVersion
from app.services.auth_service import get_current_user, require_role
from app.services.dispatch_service import DispatchService

router = APIRouter()


def _log_dict(log: NotificationLog) -> dict:
    return {
        "id": log.id,
        "mission_id": log.mission_id,
        "chauffeur_id": log.chauffeur_id,
        "status": log.status,
        "error": log.error,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
    }


@router.get("/missions/{mission_id}/brief", response_class=PlainTextResponse)
def mission_brief(
    mission_id: int,
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mission = db.get(PlanMission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return DispatchService(db).build_brief(mission)


@router.post("/missions/{mission_id}/resend")
def resend_mission(
    mission_id: int,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    mission = db.get(PlanMission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    status = DispatchService(db).dispatch_mission(mission)
    return {"mission_id": mission_id, "status": status}


@router.post("/plans/{plan_version_id}/send")
def dispatch_plan(
    plan_version_id: int,
    _user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    plan = db.get(PlanVersion, plan_version_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan version not found")
    return {"plan_version_id": plan_version_id, **DispatchService(db).dispatch_plan(plan)}


@router.get("/logs")
def dispatch_logs(
    log_date: Optional[date] = Query(None, alias="date"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(NotificationLog)
    if log_date is not None:
        query = query.filter(
            NotificationLog.sent_at >= datetime.combine(log_date, datetime.min.time()),
            NotificationLog.sent_at <= datetime.combine(log_date, datetime.max.time()),
        )
    if status is not None:
        query = query.filter(NotificationLog.status == status)
    rows = query.order_by(NotificationLog.sent_at.desc()).limit(limit).all()
    return {"logs": [_log_dict(row) for row in rows], "count": len(rows)}
