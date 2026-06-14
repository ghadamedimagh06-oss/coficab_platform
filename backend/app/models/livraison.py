"""
Livraison Model for CofICab Platform
Represents delivery/transport records from Excel files
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Livraison(Base):
    __tablename__ = "livraisons"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("planning_versions.id"), nullable=True)
    delivery_day = Column(String(20), nullable=True, index=True)
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    row_number = Column(Integer, nullable=True)
    client = Column(String(200), nullable=True)
    etd = Column(String(50), nullable=True)
    eta = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=True)
    driver = Column(String(100), nullable=False)
    vehicle = Column(String(50), nullable=False)
    start_location = Column(String(200), nullable=False)
    end_location = Column(String(200), nullable=False)
    distance_km = Column(Float, nullable=False)
    status = Column(String(20), default="pending", index=True)  # pending, in_transit, completed
    priority = Column(String(10), default="normal")  # low, normal, high, urgent
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    planning = relationship("PlanningVersion", back_populates="livraisons")

    def __repr__(self):
        return f"<Livraison(id={self.id}, driver='{self.driver}', vehicle='{self.vehicle}')>"