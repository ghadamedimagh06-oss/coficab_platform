import enum
from sqlalchemy import (
    Column, Integer, SmallInteger, Numeric, Boolean, String, Text,
    Enum, ForeignKey, DateTime, Date,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class StatutDemande(str, enum.Enum):
    NOUVELLE = "NOUVELLE"
    PLANIFIEE = "PLANIFIEE"
    EN_COURS = "EN_COURS"
    LIVREE = "LIVREE"
    ANNULEE = "ANNULEE"


class Priorite(str, enum.Enum):
    NORMALE = "NORMALE"
    HAUTE = "HAUTE"
    URGENTE = "URGENTE"


class DemandeLocal(Base):
    __tablename__ = "demandes_local"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    quantite_kg = Column(Numeric(10, 2), nullable=False)
    nombre_palettes = Column(SmallInteger)
    date_livraison = Column(Date, nullable=False, index=True)
    heure_arrivee_prevue = Column(DateTime(timezone=True))
    heure_arrivee_reelle = Column(DateTime(timezone=True))
    quantite_livree_kg = Column(Numeric(10, 2))
    commentaire = Column(Text)
    statut = Column(
        Enum(StatutDemande, name="statut_demande_enum"),
        nullable=False,
        default=StatutDemande.NOUVELLE,
    )
    priorite = Column(
        Enum(Priorite, name="priorite_enum"),
        nullable=False,
        default=Priorite.NORMALE,
    )
    livree_a_temps = Column(Boolean)
    source_import = Column(String(50))
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="demandes")
    mission_demandes = relationship("MissionDemande", back_populates="demande")
