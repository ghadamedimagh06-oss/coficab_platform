from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.planning_change_log import PlanningChangeLog
from app.models.planning_version import PlanningVersion
from app.models.planning_diff import PlanningDiff
from app.services.planning_service import PlanningService
from app.services.excel_watcher import last_detection_summary
from app.services.auth_service import get_current_user, require_role
from app.services.plan_validation_service import PlanValidationService

router = APIRouter()


class PlanningValidateRequest(BaseModel):
    planning_id: int
    user_id: int


class PlanningUpdateRequest(BaseModel):
    planning_id: int
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason_category: Optional[str] = None
    reason_text: Optional[str] = None
    user_id: int


class PlanningReviewRequest(BaseModel):
    planning_id: int
    user_id: int
    action: str
    reason: Optional[str] = None


class PlanningRevalidateRequest(BaseModel):
    planning_id: int
    user_id: int


class PlanReassignRequest(BaseModel):
    demande_id: int
    target_mission_id: int
    reason: str = "manual_edit"


@router.get("/{plan_version_id}/impact")
async def get_plan_version_impact(
    plan_version_id: int,
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PlanValidationService(db)
    try:
        return service.preview_impact(plan_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{plan_version_id}/validate")
async def validate_plan_version(
    plan_version_id: int,
    user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = PlanValidationService(db)
    try:
        return service.validate(plan_version_id, user.get("username", "planner"))
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{plan_version_id}/reassign")
async def reassign_plan_demande(
    plan_version_id: int,
    payload: PlanReassignRequest,
    user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = PlanValidationService(db)
    try:
        return service.reassign_demande(
            plan_version_id,
            payload.demande_id,
            payload.target_mission_id,
            payload.reason,
            user.get("username", "planner"),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{plan_version_id}/clone")
async def clone_plan_version(
    plan_version_id: int,
    user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = PlanValidationService(db)
    try:
        return service.clone(plan_version_id, user.get("username", "planner"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{plan_version_id}/changelog")
async def get_plan_version_changelog(
    plan_version_id: int,
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PlanValidationService(db)
    try:
        return {"changelog": service.changelog(plan_version_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/validate")
async def validate_planning(
    request: PlanningValidateRequest,
    db: Session = Depends(get_db)
):
    planning = db.query(PlanningVersion).filter(PlanningVersion.id == request.planning_id).first()
    if not planning:
        raise HTTPException(status_code=404, detail="Planning version not found")

    if planning.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Planning version must be DRAFT to validate")

    planning.status = "VALIDATED"
    planning.validated_at = datetime.now(timezone.utc)
    planning.validated_by = request.user_id
    db.add(planning)
    db.commit()
    db.refresh(planning)

    return {"message": "Planning validated successfully", "planning_id": planning.id}


@router.put("/update")
async def update_planning(
    request: PlanningUpdateRequest,
    db: Session = Depends(get_db)
):
    planning = db.query(PlanningVersion).filter(PlanningVersion.id == request.planning_id).first()
    if not planning:
        raise HTTPException(status_code=404, detail="Planning version not found")

    audit_stored = False
    if planning.status in ("VALIDATED", "IN_EXECUTION", "REVALIDATED"):
        if not request.reason_category:
            raise HTTPException(status_code=403, detail="JUSTIFICATION_REQUIRED")

        audit_entry = PlanningChangeLog(
            planning_id=request.planning_id,
            timestamp=datetime.now(timezone.utc),
            source="USER",
            modified_by=request.user_id,
            field_name=request.field_changed,
            old_value=request.old_value,
            new_value=request.new_value,
            reason=request.reason_text,
            change_type="MANUAL_UPDATE",
            user_id=request.user_id,
            reason_category=request.reason_category,
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        audit_stored = True

    return {
        "message": "Planning update recorded",
        "audit_stored": audit_stored
    }


@router.get("/{planning_id}/audit-log")
async def get_planning_audit_log(
    planning_id: int,
    db: Session = Depends(get_db)
):
    audit_entries = (
        db.query(PlanningChangeLog)
        .filter(PlanningChangeLog.planning_id == planning_id)
        .order_by(PlanningChangeLog.timestamp.desc())
        .all()
    )

    return {
        "audit_log": [
            {
                "id": entry.id,
                "planning_id": entry.planning_id,
                "field_name": entry.field_name,
                "old_value": entry.old_value,
                "new_value": entry.new_value,
                "source": entry.source,
                "modified_by": entry.modified_by,
                "reason": entry.reason,
                "change_type": entry.change_type,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            }
            for entry in audit_entries
        ]
    }


@router.get("/{planning_id}/detected-changes")
async def get_planning_detected_changes(
    planning_id: int,
    db: Session = Depends(get_db)
):
    planning = db.query(PlanningVersion).filter(PlanningVersion.id == planning_id).first()
    if not planning:
        raise HTTPException(status_code=404, detail="Planning version not found")

    service = PlanningService(db)
    return service.get_detected_changes(planning_id)


@router.get("/{planning_id}/diff-history")
async def get_planning_diff_history(
    planning_id: int,
    db: Session = Depends(get_db)
):
    service = PlanningService(db)
    return {"diff_history": service.get_diff_history(planning_id)}


@router.get("/debug-last-detection")
async def debug_last_detection():
    return last_detection_summary


@router.post("/revalidate")
async def revalidate_planning(
    request: PlanningRevalidateRequest,
    db: Session = Depends(get_db)
):
    service = PlanningService(db)
    try:
        planning = service.revalidate_planning(request.planning_id, request.user_id)
        return {
            "message": "Planning revalidated successfully",
            "planning_id": planning.id,
            "status": planning.status,
            "validated_at": planning.validated_at.isoformat() if planning.validated_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/review")
async def review_planning(
    request: PlanningReviewRequest,
    db: Session = Depends(get_db)
):
    service = PlanningService(db)
    action = request.action.lower()

    if action == "reject":
        try:
            planning = service.reject_planning_changes(request.planning_id, request.user_id, request.reason)
            return {
                "message": "Planning changes rejected",
                "planning_id": planning.id,
                "status": planning.status,
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if action == "request":
        planning = db.query(PlanningVersion).filter(PlanningVersion.id == request.planning_id).first()
        if not planning:
            raise HTTPException(status_code=404, detail="Planning version not found")
        if planning.status != "MODIFIED_AFTER_VALIDATION":
            raise HTTPException(status_code=400, detail="Planning must be modified after validation to request review")
        planning.status = "PENDING_REVIEW"
        planning.last_review_at = datetime.now(timezone.utc)
        planning.reviewed_by = request.user_id
        db.add(planning)
        db.commit()
        return {
            "message": "Planning marked as pending review",
            "planning_id": planning.id,
            "status": planning.status,
        }

    if action == "approve":
        try:
            planning = service.revalidate_planning(request.planning_id, request.user_id)
            return {
                "message": "Planning changes approved and revalidated",
                "planning_id": planning.id,
                "status": planning.status,
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    raise HTTPException(status_code=400, detail="Unknown review action")


@router.get("/{planning_id}/impact-preview")
async def get_planning_impact_preview(
    planning_id: int,
    field: str = Query(...),
    new_value: str = Query(...),
    db: Session = Depends(get_db)
):
    planning = db.query(PlanningVersion).filter(PlanningVersion.id == planning_id).first()
    if not planning:
        raise HTTPException(status_code=404, detail="Planning version not found")

    warning_text = f"Changing {field} to {new_value} may delay route R12 by 25 minutes."

    return {
        "affected_deliveries": 3,
        "affected_routes": ["R12", "R07"],
        "affected_drivers": ["Driver A", "Driver C"],
        "estimated_delay_minutes": 25,
        "warning": warning_text
    }
