from sqlalchemy import Column, Integer, Date, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PlanningVersion(Base):
    __tablename__ = "planning_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'VALIDATED', 'MODIFIED_AFTER_VALIDATION', 'PENDING_REVIEW', 'REVALIDATED', 'REJECTED_CHANGES', 'IN_EXECUTION', 'ARCHIVED')",
            name="ck_planning_version_status"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    week = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, server_default="DRAFT")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    last_review_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    file_name = Column(String(255), nullable=True)
    excel_path = Column(String(500), nullable=True)
    source = Column(String(50), nullable=False, server_default="WATCHDOG_SYSTEM")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    livraisons = relationship("Livraison", back_populates="planning", cascade="all, delete-orphan")
    audit_logs = relationship("PlanningChangeLog", back_populates="planning", cascade="all, delete-orphan")
    diffs = relationship("PlanningDiff", back_populates="planning", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PlanningVersion(id={self.id}, week={self.week}, status='{self.status}')>"
