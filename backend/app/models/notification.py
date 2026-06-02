from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True)
    mission_id = Column(Integer, ForeignKey("plan_mission.id"), nullable=False)
    chauffeur_id = Column(Integer, ForeignKey("chauffeurs.id"), nullable=False)
    status = Column(String(20), nullable=False)
    error = Column(Text)
    body = Column(Text)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    mission = relationship("PlanMission")
    chauffeur = relationship("Chauffeur")
