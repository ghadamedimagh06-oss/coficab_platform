"""
API Routes for Delivery Split Workflow (Option 4: Human-in-the-Loop)
Endpoints:
  - POST /planning/oversized/{delivery_id}/propose-split
  - POST /planning/oversized/{delivery_id}/decision
  - GET /planning/oversized/{delivery_id}/audit
  - GET /planning/oversized/pending
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import json
import logging

from app.database import get_db
from app.models.delivery_split import (
    DeliverySplit,
    DeliverySplitAudit,
    OversizedDeliveryState,
    SplitProposalSchema,
    SplitDecisionSchema,
    SubDeliverySchema,
    DeliverySplitResponseSchema,
    DeliverySplitAuditResponseSchema,
)
from app.models.livraison import Livraison
from app.models.transport import User
from app.services.split_strategy import SplitStrategy, DeliveryInfo, VehicleCapacity
from app.routes.auth import get_current_user

router = APIRouter(prefix="/planning/oversized", tags=["delivery-split"])
logger = logging.getLogger(__name__)


# ============================================================================
# 1. PROPOSE SPLIT - Algorithm calculates optimal split
# ============================================================================

@router.post("/{delivery_id}/propose-split")
async def propose_split(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect capacity violation and propose optimal split.
    Triggered automatically by watchdog at 15:00 or manually by supervisor.
    
    Creates a DeliverySplitAudit record in DETECTED state and notifies dashboard.
    """
    # Step 1: Fetch delivery
    delivery = db.query(Livraison).filter(Livraison.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")
    
    # Step 2: Check if already proposed (avoid duplicates)
    existing = db.query(DeliverySplitAudit).filter(
        DeliverySplitAudit.original_delivery_id == delivery_id,
        DeliverySplitAudit.state.in_([
            OversizedDeliveryState.PROPOSED.value,
            OversizedDeliveryState.VALIDATED.value,
        ])
    ).first()
    
    if existing:
        return {
            "status": "already_proposed",
            "message": f"Delivery {delivery_id} already has pending proposal",
            "existing_audit_id": existing.id
        }
    
    # Step 3: Get vehicle capacity (hardcoded for now, should be from DB)
    # TODO: Fetch from vehicles table
    vehicles = [
        VehicleCapacity(vehicle_id="V1", vehicle_type="8T", capacity=8000),
        VehicleCapacity(vehicle_id="V2", vehicle_type="12T", capacity=12000),
        VehicleCapacity(vehicle_id="V3", vehicle_type="20T", capacity=20000),
    ]
    
    max_vehicle_capacity = max(v.capacity for v in vehicles)
    
    # Step 4: Check if oversized
    if delivery.quantity <= max_vehicle_capacity:
        return {
            "status": "no_split_needed",
            "message": f"Delivery fits single vehicle (qty {delivery.quantity} ≤ capacity {max_vehicle_capacity})",
            "delivery_id": delivery_id
        }
    
    # Step 5: Run split algorithm
    split_strategy = SplitStrategy(vehicles)
    delivery_info = DeliveryInfo(
        id=delivery.id,
        quantity=delivery.quantity,
        unit_increment=24,  # TODO: Get from delivery metadata
        client_id=delivery.client or "UNKNOWN",
        product_type="Cable",  # TODO: Get from delivery metadata
        notes=delivery.notes
    )
    
    proposal = split_strategy.compute_split(delivery_info, max_vehicle_capacity)
    
    # Step 6: Create audit record (DETECTED → PROPOSED state)
    audit = DeliverySplitAudit(
        original_delivery_id=delivery_id,
        state=OversizedDeliveryState.DETECTED.value,
        detected_at=datetime.utcnow(),
        proposal_json=json.loads(proposal.model_dump_json()),
        max_vehicle_capacity=max_vehicle_capacity,
        proposed_splits_count=len(proposal.proposed_sub_deliveries),
    )
    
    db.add(audit)
    db.commit()
    db.refresh(audit)
    
    # Step 7: Publish to dashboard (Redis Pub/Sub would go here)
    # For now, we just return the proposal
    logger.info(
        f"[SPLIT] Delivery {delivery_id}: DETECTED oversized, "
        f"proposing {len(proposal.proposed_sub_deliveries)} splits"
    )
    
    # Update state to PROPOSED
    audit.state = OversizedDeliveryState.PROPOSED.value
    db.commit()
    
    return {
        "status": "proposed",
        "audit_id": audit.id,
        "proposal": proposal,
        "actions": ["VALIDATE", "MODIFY", "REJECT"]
    }


# ============================================================================
# 2. MAKE DECISION - Transport manager approves/modifies/rejects
# ============================================================================

@router.post("/{delivery_id}/decision")
async def apply_decision(
    delivery_id: int,
    decision: SplitDecisionSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transport manager makes explicit decision on split proposal.
    Actions:
      - VALIDATE: Accept proposed split and create sub-deliveries
      - MODIFY: Accept split but with manually adjusted quantities
      - REJECT: Decline split → create exception alert for external location
    """
    # Step 1: Fetch latest audit record
    audit = db.query(DeliverySplitAudit).filter(
        DeliverySplitAudit.original_delivery_id == delivery_id,
        DeliverySplitAudit.state == OversizedDeliveryState.PROPOSED.value
    ).order_by(DeliverySplitAudit.id.desc()).first()
    
    if not audit:
        raise HTTPException(
            status_code=404,
            detail=f"No pending split proposal for delivery {delivery_id}"
        )
    
    # Step 2: Fetch delivery
    delivery = db.query(Livraison).filter(Livraison.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")
    
    # Step 3: Process decision
    if decision.action == "VALIDATE":
        return await _validate_split(delivery, audit, current_user, db)
    
    elif decision.action == "MODIFY":
        if not decision.modified_quantities:
            raise HTTPException(
                status_code=400,
                detail="MODIFY action requires modified_quantities array"
            )
        return await _modify_split(delivery, audit, decision.modified_quantities, current_user, db)
    
    elif decision.action == "REJECT":
        return await _reject_split(delivery, audit, decision.reason, current_user, db)
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {decision.action}. Must be VALIDATE, MODIFY, or REJECT"
        )


async def _validate_split(
    delivery: Livraison,
    audit: DeliverySplitAudit,
    current_user: User,
    db: Session
):
    """VALIDATE: Accept proposed split and create sub-deliveries"""
    proposal = SplitProposalSchema(**audit.proposal_json)
    
    # Create DeliverySplit records for each sub-delivery
    sub_delivery_ids = []
    for sub in proposal.proposed_sub_deliveries:
        split_record = DeliverySplit(
            original_delivery_id=delivery.id,
            split_sequence=sub.sequence,
            quantity=sub.quantity,
            unit_increment=sub.unit_increment,
            state=OversizedDeliveryState.VALIDATED.value,
            validated_at=datetime.utcnow(),
            validated_by=current_user.id,
            proposal_json=json.loads(sub.model_dump_json()),
            constraint_check_json=proposal.constraint_check
        )
        db.add(split_record)
        db.flush()
        sub_delivery_ids.append(split_record.id)
    
    # Update audit record
    audit.state = OversizedDeliveryState.VALIDATED.value
    audit.decision_action = "VALIDATE"
    audit.decided_at = datetime.utcnow()
    audit.decided_by = current_user.id
    audit.linked_sub_deliveries_json = sub_delivery_ids
    
    db.commit()
    
    logger.info(
        f"[SPLIT] Delivery {delivery.id}: VALIDATED split into "
        f"{len(sub_delivery_ids)} sub-deliveries by user {current_user.id}"
    )
    
    return {
        "status": "validated",
        "delivery_id": delivery.id,
        "sub_deliveries_created": len(sub_delivery_ids),
        "sub_delivery_ids": sub_delivery_ids,
        "message": f"Split approved: {len(sub_delivery_ids)} sub-deliveries created"
    }


async def _modify_split(
    delivery: Livraison,
    audit: DeliverySplitAudit,
    modified_quantities: List[int],
    current_user: User,
    db: Session
):
    """MODIFY: Accept split with manually adjusted quantities"""
    proposal = SplitProposalSchema(**audit.proposal_json)
    
    # Validate modified quantities
    is_valid, messages = SplitStrategy([]).validate_modified_quantities(
        original_qty=delivery.quantity,
        modified_quantities=modified_quantities,
        unit_increment=proposal.proposed_sub_deliveries[0].unit_increment,
        capacity=audit.max_vehicle_capacity
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid modified quantities",
                "constraints": messages
            }
        )
    
    # Create DeliverySplit records with modified quantities
    sub_delivery_ids = []
    for seq, qty in enumerate(modified_quantities, 1):
        split_record = DeliverySplit(
            original_delivery_id=delivery.id,
            split_sequence=seq,
            quantity=qty,
            unit_increment=proposal.proposed_sub_deliveries[0].unit_increment,
            state=OversizedDeliveryState.MODIFIED.value,
            validated_at=datetime.utcnow(),
            validated_by=current_user.id,
            proposal_json={
                "sequence": seq,
                "quantity": qty,
                "original_proposal_qty": proposal.proposed_sub_deliveries[seq - 1].quantity
            },
            constraint_check_json=messages
        )
        db.add(split_record)
        db.flush()
        sub_delivery_ids.append(split_record.id)
    
    # Update audit record
    audit.state = OversizedDeliveryState.MODIFIED.value
    audit.decision_action = "MODIFY"
    audit.decided_at = datetime.utcnow()
    audit.decided_by = current_user.id
    audit.modified_quantities_json = modified_quantities
    audit.linked_sub_deliveries_json = sub_delivery_ids
    
    db.commit()
    
    logger.info(
        f"[SPLIT] Delivery {delivery.id}: MODIFIED split by user {current_user.id}, "
        f"quantities: {modified_quantities}"
    )
    
    return {
        "status": "modified",
        "delivery_id": delivery.id,
        "sub_deliveries_created": len(sub_delivery_ids),
        "sub_delivery_ids": sub_delivery_ids,
        "modified_quantities": modified_quantities,
        "constraints": messages,
        "message": f"Split modified: {len(sub_delivery_ids)} sub-deliveries created with custom quantities"
    }


async def _reject_split(
    delivery: Livraison,
    audit: DeliverySplitAudit,
    reason: str,
    current_user: User,
    db: Session
):
    """REJECT: Decline split, create exception alert for external location"""
    # Update audit record
    audit.state = OversizedDeliveryState.REJECTED.value
    audit.decision_action = "REJECT"
    audit.decided_at = datetime.utcnow()
    audit.decided_by = current_user.id
    audit.decision_reason = reason
    
    # Create exception alert (would be linked to external location/transport service)
    # TODO: Integrate with exception alert system
    audit.exception_alert_created = True
    audit.exception_alert_id = f"EXC-{delivery.id}-{datetime.utcnow().timestamp()}"
    
    db.commit()
    
    logger.info(
        f"[SPLIT] Delivery {delivery.id}: REJECTED by user {current_user.id}, "
        f"reason: {reason}"
    )
    
    return {
        "status": "rejected",
        "delivery_id": delivery.id,
        "exception_alert_id": audit.exception_alert_id,
        "reason": reason,
        "message": "Split rejected. Exception alert created for external transport service."
    }


# ============================================================================
# 3. GET AUDIT TRAIL
# ============================================================================

@router.get("/{delivery_id}/audit")
async def get_split_audit(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full audit trail for a delivery's split workflow"""
    audits = db.query(DeliverySplitAudit).filter(
        DeliverySplitAudit.original_delivery_id == delivery_id
    ).order_by(DeliverySplitAudit.created_at.desc()).all()
    
    if not audits:
        raise HTTPException(
            status_code=404,
            detail=f"No split audit records for delivery {delivery_id}"
        )
    
    return {
        "delivery_id": delivery_id,
        "audit_count": len(audits),
        "audits": [
            DeliverySplitAuditResponseSchema.from_orm(audit).dict() for audit in audits
        ]
    }


# ============================================================================
# 4. GET PENDING SPLITS (Dashboard Widget)
# ============================================================================

@router.get("/pending")
async def get_pending_splits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all pending split proposals awaiting transport manager decision.
    Used by dashboard to populate alerts and action items.
    """
    pending = db.query(DeliverySplitAudit).filter(
        DeliverySplitAudit.state == OversizedDeliveryState.PROPOSED.value
    ).order_by(DeliverySplitAudit.detected_at.desc()).all()
    
    result = []
    for audit in pending:
        delivery = db.query(Livraison).filter(Livraison.id == audit.original_delivery_id).first()
        proposal = SplitProposalSchema(**audit.proposal_json)
        
        result.append({
            "audit_id": audit.id,
            "delivery_id": delivery.id,
            "client": delivery.client if delivery else "UNKNOWN",
            "quantity": delivery.quantity if delivery else audit.proposal_json["total_quantity"],
            "detected_at": audit.detected_at.isoformat(),
            "proposal": proposal,
            "status": "AWAITING_DECISION",
            "time_pending_seconds": (datetime.utcnow() - audit.detected_at).total_seconds()
        })
    
    return {
        "pending_count": len(result),
        "pending_splits": result
    }
