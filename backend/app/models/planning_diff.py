from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PlanningDiff(Base):
    __tablename__ = "planning_diffs"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("planning_versions.id"), nullable=False)
    delivery_id = Column(Integer, ForeignKey("livraisons.id"), nullable=True)
    delivery_day = Column(String(20), nullable=True)
    row_number = Column(Integer, nullable=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    impact_eta = Column(Float, nullable=True)
    impact_cost = Column(Float, nullable=True)
    impact_risk = Column(String(50), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_j_plus_1 = Column(Boolean, nullable=False, default=False)
    ignored_reason = Column(Text, nullable=True)

    planning = relationship("PlanningVersion", back_populates="diffs")

    def __repr__(self):
        return f"<PlanningDiff(id={self.id}, planning_id={self.planning_id}, field_name='{self.field_name}')>"
