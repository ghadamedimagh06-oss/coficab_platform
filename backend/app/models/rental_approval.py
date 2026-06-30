from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class RentalApproval(Base):
    __tablename__ = "rental_approval"
    __table_args__ = (
        UniqueConstraint("plan_id", "recommendation_id", name="uq_rental_approval_plan_recommendation"),
    )

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(100), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    recommendation_id = Column(String(100), nullable=False)
    rental_profile = Column(String(50), nullable=False)
    estimated_cost_eur = Column(Numeric(10, 2), nullable=False)
    approved_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
