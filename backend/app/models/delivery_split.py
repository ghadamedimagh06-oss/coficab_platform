"""
Delivery Split Model for Human-in-the-Loop Validation Workflow
Supports Option 4: Split Assisté par Workflow de Validation
IATF Traceability: every split decision is audited
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from enum import Enum
from typing import Optional, List
from datetime import datetime


class OversizedDeliveryState(str, Enum):
    """State machine for oversized delivery handling workflow"""
    DETECTED = "DETECTED"           # Algorithm identified capacity overflow
    PROPOSED = "PROPOSED"           # Split calculated, awaiting UI validation
    VALIDATED = "VALIDATED"         # Transport manager approved split
    MODIFIED = "MODIFIED"           # Manager adjusted quantities manually
    REJECTED = "REJECTED"           # Refusal → exceptional transport (external location)
    PLANNED = "PLANNED"             # Integrated into final VRPTW
    EXCEPTION = "EXCEPTION"         # Out of scope (external location required)


class DeliverySplit(Base):
    """Persistence layer for split sub-deliveries"""
    __tablename__ = "delivery_splits"

    id = Column(Integer, primary_key=True, index=True)
    original_delivery_id = Column(Integer, ForeignKey("livraisons.id"), nullable=False)
    parent_split_id = Column(Integer, ForeignKey("delivery_splits.id"), nullable=True)
    split_sequence = Column(Integer, nullable=False)  # 1, 2, 3...
    quantity = Column(Integer, nullable=False)
    unit_increment = Column(Integer, nullable=True)  # e.g., 24 for palettes of 24 bobines
    
    # Metadata
    state = Column(String(20), nullable=False, default=OversizedDeliveryState.PROPOSED.value)
    proposed_at = Column(DateTime(timezone=True), server_default=func.now())
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Audit trail
    proposal_json = Column(JSON, nullable=True)  # Full proposal snapshot
    decision_reason = Column(Text, nullable=True)
    constraint_check_json = Column(JSON, nullable=True)  # Validation constraints passed
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    original_delivery = relationship("Livraison", foreign_keys=[original_delivery_id])
    validated_by_user = relationship("User", foreign_keys=[validated_by])
    child_splits = relationship("DeliverySplit", remote_side=[id], backref="parent")

    def __repr__(self):
        return f"<DeliverySplit(id={self.id}, original_id={self.original_delivery_id}, seq={self.split_sequence}, qty={self.quantity}, state={self.state})>"


class DeliverySplitAudit(Base):
    """Full audit trail for IATF 16949 compliance"""
    __tablename__ = "delivery_split_audits"

    id = Column(Integer, primary_key=True, index=True)
    original_delivery_id = Column(Integer, ForeignKey("livraisons.id"), nullable=False, index=True)
    
    # State progression
    state = Column(String(20), nullable=False, index=True)  # Current state
    detected_at = Column(DateTime(timezone=True), nullable=False)
    
    # Proposal (calculated by algorithm)
    proposal_json = Column(JSON, nullable=False)  # Full SplitProposal snapshot
    max_vehicle_capacity = Column(Integer, nullable=False)
    proposed_splits_count = Column(Integer, nullable=False)
    
    # Decision (made by human)
    decision_action = Column(String(20), nullable=True)  # VALIDATE, MODIFY, REJECT
    decision_reason = Column(Text, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    
    # Modifications (if decision_action == MODIFY)
    modified_quantities_json = Column(JSON, nullable=True)
    
    # System integration
    linked_sub_deliveries_json = Column(JSON, nullable=True)  # IDs of created splits
    is_integrated_to_vrptw = Column(Boolean, default=False)
    vrptw_replan_triggered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Exception handling (if decision_action == REJECT)
    exception_alert_created = Column(Boolean, default=False)
    exception_alert_id = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    original_delivery = relationship("Livraison", foreign_keys=[original_delivery_id])
    decided_by_user = relationship("User", foreign_keys=[decided_by])

    def __repr__(self):
        return f"<DeliverySplitAudit(id={self.id}, delivery_id={self.original_delivery_id}, state={self.state})>"


# Pydantic Schemas for API

from pydantic import BaseModel


class SubDeliverySchema(BaseModel):
    """Single sub-delivery in a split proposal"""
    sequence: int
    quantity: int
    unit_increment: int
    estimated_vehicle_type: Optional[str] = None


class SplitProposalSchema(BaseModel):
    """Algorithm-generated proposal for split"""
    original_delivery_id: int
    total_quantity: int
    max_vehicle_capacity: int
    proposed_sub_deliveries: List[SubDeliverySchema]
    constraint_check: List[str]  # ["Multiple palette OK", "Bobine entière OK", ...]
    algorithm_notes: Optional[str] = None

    class Config:
        from_attributes = True


class SplitDecisionSchema(BaseModel):
    """Transport manager's decision on split proposal"""
    delivery_id: int
    action: str  # "VALIDATE", "MODIFY", "REJECT"
    reason: str
    modified_quantities: Optional[List[int]] = None  # If action == MODIFY

    class Config:
        from_attributes = True


class DeliverySplitResponseSchema(BaseModel):
    """Response for split creation/update"""
    id: int
    original_delivery_id: int
    split_sequence: int
    quantity: int
    state: str
    validated_at: Optional[datetime]
    validated_by: Optional[int]
    decision_reason: Optional[str]

    class Config:
        from_attributes = True


class DeliverySplitAuditResponseSchema(BaseModel):
    """Full audit trail response"""
    id: int
    original_delivery_id: int
    state: str
    detected_at: datetime
    proposal_json: dict
    decision_action: Optional[str]
    decision_reason: Optional[str]
    decided_by: Optional[int]
    decided_at: Optional[datetime]
    exception_alert_created: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
