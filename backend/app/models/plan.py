import enum
from sqlalchemy import (
    Column, Integer, SmallInteger, Numeric, String, Text,
    Enum, ForeignKey, DateTime, Date, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class StatutPlan(str, enum.Enum):
    DRAFT = "DRAFT"
    EN_REVUE = "EN_REVUE"
    VALIDE = "VALIDE"
    EXECUTE = "EXECUTE"
    CLOTURE = "CLOTURE"


class Periode(str, enum.Enum):
    JOUR = "JOUR"
    SEMAINE = "SEMAINE"
    MOIS = "MOIS"


class StatutMission(str, enum.Enum):
    PLANIFIEE = "PLANIFIEE"
    EN_COURS = "EN_COURS"
    TERMINEE = "TERMINEE"
    ANNULEE = "ANNULEE"


class ModeMission(str, enum.Enum):
    NORMAL = "NORMAL"
    PREMIUM = "PREMIUM"


class PlanVersion(Base):
    __tablename__ = "plan_version"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False)
    version_number = Column(SmallInteger, nullable=False)
    periode = Column(Enum(Periode, name="periode_enum"), nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    statut_plan = Column(
        Enum(StatutPlan, name="statut_plan_enum"),
        nullable=False,
        default=StatutPlan.DRAFT,
    )
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    date_validation = Column(DateTime(timezone=True))
    valide_par = Column(String(100))
    commentaire = Column(Text)

    missions = relationship("PlanMission", back_populates="plan_version", cascade="all, delete-orphan")
    change_logs = relationship("app.models.plan.PlanningChangeLog", back_populates="plan_version", cascade="all, delete-orphan")


class PlanMission(Base):
    __tablename__ = "plan_mission"

    id = Column(Integer, primary_key=True)
    plan_version_id = Column(Integer, ForeignKey("plan_version.id", ondelete="CASCADE"), nullable=False, index=True)
    camion_id = Column(Integer, ForeignKey("camions.id"), nullable=False)
    chauffeur_id = Column(Integer, ForeignKey("chauffeurs.id"), nullable=False)
    date_mission = Column(Date, nullable=False, index=True)
    heure_sortie_prevue = Column(DateTime(timezone=True))
    heure_sortie_reelle = Column(DateTime(timezone=True))
    heure_retour_prevue = Column(DateTime(timezone=True))
    heure_retour_reelle = Column(DateTime(timezone=True))
    statut = Column(
        Enum(StatutMission, name="statut_mission_enum"),
        nullable=False,
        default=StatutMission.PLANIFIEE,
    )
    mode = Column(
        Enum(ModeMission, name="mode_mission_enum"),
        nullable=False,
        default=ModeMission.NORMAL,
    )
    km_parcourus = Column(Numeric(8, 2))
    km_a_vide = Column(Numeric(8, 2))
    charge_kg = Column(Numeric(10, 2))
    charge_palettes = Column(SmallInteger)
    fuel_consomme_l = Column(Numeric(8, 2))
    cout_consommables_eur = Column(Numeric(10, 2), default=0)
    cout_emballage_eur = Column(Numeric(10, 2), default=0)
    cout_transport_eur = Column(Numeric(10, 2), default=0)
    cout_premium_eur = Column(Numeric(10, 2), default=0)
    load_eff_kg_pct = Column(Numeric(5, 2))
    load_eff_pallets_pct = Column(Numeric(5, 2))
    load_eff_pct = Column(Numeric(5, 2))

    plan_version = relationship("PlanVersion", back_populates="missions")
    camion = relationship("Camion", back_populates="missions")
    chauffeur = relationship("Chauffeur", back_populates="missions")
    mission_demandes = relationship("MissionDemande", back_populates="mission", cascade="all, delete-orphan")
    evenements = relationship("EvenementAlea", back_populates="mission")


class MissionDemande(Base):
    __tablename__ = "mission_demande"

    id = Column(Integer, primary_key=True)
    mission_id = Column(Integer, ForeignKey("plan_mission.id", ondelete="CASCADE"), nullable=False, index=True)
    demande_id = Column(Integer, ForeignKey("demandes_local.id"), nullable=False, index=True)
    ordre_livraison = Column(SmallInteger, nullable=False)
    eta_prevue = Column(DateTime(timezone=True))
    eta_reelle = Column(DateTime(timezone=True))
    statut = Column(
        Enum("NOUVELLE", "PLANIFIEE", "EN_COURS", "LIVREE", "ANNULEE", name="statut_demande_enum"),
        nullable=False,
        default="PLANIFIEE",
    )

    mission = relationship("PlanMission", back_populates="mission_demandes")
    demande = relationship("DemandeLocal", back_populates="mission_demandes")


class PlanningChangeLog(Base):
    __tablename__ = "planning_change_log"

    id = Column(Integer, primary_key=True)
    plan_version_id = Column(Integer, ForeignKey("plan_version.id"), nullable=False)
    field_changed = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    reason_category = Column(String(50))
    reason_text = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    plan_version = relationship("app.models.plan.PlanVersion", back_populates="change_logs")
