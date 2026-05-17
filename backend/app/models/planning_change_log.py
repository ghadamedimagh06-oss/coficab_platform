from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PlanningChangeLog(Base):
    __tablename__ = "planning_change_logs"
    __table_args__ = (
        CheckConstraint(
            "source IN ('USER', 'WATCHDOG_SYSTEM')",
            name="ck_planning_change_log_source"
        ),
        CheckConstraint(
            "change_type IN ('MANUAL_UPDATE', 'EXCEL_SYNC', 'REVALIDATION')",
            name="ck_planning_change_log_change_type"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("planning_versions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String(50), nullable=False, server_default="WATCHDOG_SYSTEM")
    modified_by = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    change_type = Column(String(50), nullable=False, server_default="EXCEL_SYNC")
    reason_category = Column(String(50), nullable=True)
    reason_text = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True)

    planning = relationship("PlanningVersion", back_populates="audit_logs")

    def __repr__(self):
        return f"<PlanningChangeLog(id={self.id}, planning_id={self.planning_id}, field_name='{self.field_name}')>"
