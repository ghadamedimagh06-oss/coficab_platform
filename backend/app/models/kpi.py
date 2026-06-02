import enum
from sqlalchemy import (
    Column, Integer, SmallInteger, Numeric, String, Text,
    Enum, ForeignKey, DateTime, Date, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class KpiFrequence(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class KpiDirection(str, enum.Enum):
    UP = "UP"      # higher is better
    DOWN = "DOWN"  # lower is better


class KpiStatus(str, enum.Enum):
    OK = "OK"
    WARN = "WARN"
    ALERT = "ALERT"
    NA = "NA"


class KpiDefinition(Base):
    __tablename__ = "kpi_definition"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    nom = Column(Text, nullable=False)
    description = Column(Text)
    unite = Column(String(20), nullable=False)
    frequence = Column(Enum(KpiFrequence, name="kpi_frequence_enum"), nullable=False)
    direction = Column(Enum(KpiDirection, name="kpi_direction_enum"), nullable=False)
    target_2025 = Column(Numeric(10, 4))
    green_min = Column(Numeric(10, 4))
    yellow_min = Column(Numeric(10, 4))
    green_max = Column(Numeric(10, 4))
    yellow_max = Column(Numeric(10, 4))
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    journalier = relationship("KpiJournalier", back_populates="kpi_def")
    mensuel = relationship("KpiMensuel", back_populates="kpi_def")


class KpiJournalier(Base):
    __tablename__ = "kpi_journalier"

    id = Column(Integer, primary_key=True)
    kpi_def_id = Column(Integer, ForeignKey("kpi_definition.id"), nullable=False)
    date_mesure = Column(Date, nullable=False)
    plant = Column(String(50))
    valeur = Column(Numeric(12, 4))
    color = Column(String(10))
    qte_total_kg = Column(Numeric(12, 2))
    qte_livree_kg = Column(Numeric(12, 2))
    qte_a_temps_kg = Column(Numeric(12, 2))
    fuel_consomme_l = Column(Numeric(12, 2))
    km_parcourus = Column(Numeric(12, 2))
    km_a_vide = Column(Numeric(12, 2))
    nb_incidents = Column(Integer)
    nb_missions = Column(Integer)
    cout_total_eur = Column(Numeric(12, 2))
    date_calcul = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("kpi_def_id", "date_mesure", "plant"),)

    kpi_def = relationship("KpiDefinition", back_populates="journalier")


class KpiMensuel(Base):
    __tablename__ = "kpi_mensuel"

    id = Column(Integer, primary_key=True)
    kpi_def_id = Column(Integer, ForeignKey("kpi_definition.id"), nullable=False)
    annee = Column(SmallInteger, nullable=False)
    mois = Column(SmallInteger, nullable=False)
    plant = Column(String(50))
    valeur = Column(Numeric(12, 4))
    target = Column(Numeric(12, 4))
    status = Column(
        Enum(KpiStatus, name="kpi_status_enum"),
        nullable=False,
        default=KpiStatus.NA,
    )
    color = Column(String(10))
    date_calcul = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("kpi_def_id", "annee", "mois", "plant"),)

    kpi_def = relationship("KpiDefinition", back_populates="mensuel")
