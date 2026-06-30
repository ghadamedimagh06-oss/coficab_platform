import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PermisType(str, enum.Enum):
    B = "B"
    C = "C"
    CE = "CE"
    D = "D"


class ChauffeurStatus(str, enum.Enum):
    ACTIF = "ACTIF"
    CONGE = "CONGE"
    ARRET_MALADIE = "ARRET_MALADIE"
    INACTIF = "INACTIF"


class Chauffeur(Base):
    __tablename__ = "chauffeurs"

    id = Column(Integer, primary_key=True)  # matricule interne
    full_name = Column(String, nullable=False)
    phone = Column(String(30))
    permis_type = Column(Enum(PermisType, name="permis_type_enum"), nullable=False)
    permis_numero = Column(String(50), unique=True)
    status = Column(
        Enum(ChauffeurStatus, name="chauffeur_status_enum"),
        nullable=False,
        default=ChauffeurStatus.ACTIF,
    )
    camion_defaut_id = Column(Integer, ForeignKey("camions.id"), unique=True)
    shift_start = Column(Time)
    shift_end = Column(Time)
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    camion_defaut = relationship("Camion", foreign_keys=[camion_defaut_id])
    missions = relationship("PlanMission", back_populates="chauffeur")
