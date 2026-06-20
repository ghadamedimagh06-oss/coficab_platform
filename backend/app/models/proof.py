"""
Electronic Proof of Delivery (ePOD) record — see docs/TMS_ROADMAP.md §4/§5.

One row per delivery confirmation (or exception). This is the input that turns
forecast KPIs into *actuals*: confirming a delivery advances the linked
DemandeLocal to LIVREE with quantite_livree_kg / livree_a_temps, which the
OTIF/OTD live computers read.
"""
import enum
from sqlalchemy import (
    Column, Integer, Numeric, String, Text, Boolean, Enum, ForeignKey, DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PodStatus(str, enum.Enum):
    LIVREE = "LIVREE"        # delivered in full
    PARTIELLE = "PARTIELLE"  # delivered, short quantity
    REFUSEE = "REFUSEE"      # client refused / not delivered


class LivraisonPreuve(Base):
    __tablename__ = "livraison_preuve"

    id = Column(Integer, primary_key=True)
    mission_demande_id = Column(
        Integer, ForeignKey("mission_demande.id", ondelete="CASCADE"), nullable=False, index=True
    )
    demande_id = Column(Integer, ForeignKey("demandes_local.id"), nullable=False, index=True)
    statut = Column(Enum(PodStatus, name="pod_status_enum"), nullable=False, default=PodStatus.LIVREE)
    delivered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    quantite_livree_kg = Column(Numeric(10, 2))
    on_time = Column(Boolean)
    signataire = Column(String(120))   # name of the person who signed/received
    photo_url = Column(Text)           # link/data-uri to a delivery photo
    notes = Column(Text)
    created_by = Column(String(80))    # dispatcher/driver username
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    mission_demande = relationship("MissionDemande")
