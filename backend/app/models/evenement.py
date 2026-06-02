import enum
from sqlalchemy import (
    Column, Integer, Boolean, Text, Enum, ForeignKey, DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class EvenementType(str, enum.Enum):
    PANNE_VEHICULE = "PANNE_VEHICULE"
    RETARD_TRAFIC = "RETARD_TRAFIC"
    CLIENT_INDISPONIBLE = "CLIENT_INDISPONIBLE"
    DEPASSEMENT_CAPACITE = "DEPASSEMENT_CAPACITE"
    DEMANDE_LAST_MINUTE = "DEMANDE_LAST_MINUTE"
    CLIENT_COMPLAINT = "CLIENT_COMPLAINT"


class EvenementAlea(Base):
    __tablename__ = "evenement_alea"

    id = Column(Integer, primary_key=True)
    plan_version_id = Column(Integer, ForeignKey("plan_version.id"))
    mission_id = Column(Integer, ForeignKey("plan_mission.id"))
    demande_id = Column(Integer, ForeignKey("demandes_local.id"))
    type = Column(Enum(EvenementType, name="evenement_type_enum"), nullable=False)
    description = Column(Text)
    date_evenement = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    impact_delai_min = Column(Integer, default=0)
    resolu = Column(Boolean, default=False)
    date_resolution = Column(DateTime(timezone=True))
    cause = Column(Text)

    mission = relationship("PlanMission", back_populates="evenements")
