import enum
from sqlalchemy import Column, Integer, String, Numeric, SmallInteger, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CamionType(str, enum.Enum):
    SEMI = "SEMI"
    PORTEUR = "PORTEUR"
    FOURGON = "FOURGON"
    TAUTLINER = "TAUTLINER"


class CamionStatus(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    EN_MISSION = "EN_MISSION"
    MAINTENANCE = "MAINTENANCE"
    PANNE = "PANNE"


class Camion(Base):
    __tablename__ = "camions"

    id = Column(Integer, primary_key=True)
    plate_number = Column(String(20), unique=True, nullable=False)
    type = Column(Enum(CamionType, name="camion_type_enum"), nullable=False)
    capacite_kg = Column(Numeric(10, 2), nullable=False)
    max_palettes = Column(SmallInteger, nullable=False)
    status = Column(
        Enum(CamionStatus, name="camion_status_enum"),
        nullable=False,
        default=CamionStatus.DISPONIBLE,
    )
    consommation_base_l_100km = Column(Numeric(5, 2))
    chauffeur_defaut_id = Column(Integer, ForeignKey("chauffeurs.id"))
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    missions = relationship("PlanMission", back_populates="camion")
    chauffeur_defaut = relationship(
        "Chauffeur", foreign_keys=[chauffeur_defaut_id], post_update=True
    )
