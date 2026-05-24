from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class TransportTracking(Base):
    __tablename__ = "transport_tracking"

    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(String(100), nullable=False)
    status = Column(String(50), nullable=True)
    location = Column(Text, nullable=True)  # store JSON as text
    eta_hours = Column(Float, nullable=True)
    distance_remaining = Column(Float, nullable=True)
    source = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<TransportTracking(id={self.id}, transport_id={self.transport_id})>"
