"""Database Models Package — Coficab ERD"""

# Reference tables
from .camion import Camion, CamionType, CamionStatus
from .chauffeur import Chauffeur, PermisType, ChauffeurStatus
from .client import Client

# Operational tables
from .demande import DemandeLocal, StatutDemande, Priorite
from .plan import PlanVersion, PlanMission, MissionDemande, PlanningChangeLog
from .plan import StatutPlan, StatutMission, ModeMission, Periode
from .evenement import EvenementAlea, EvenementType
from .proof import LivraisonPreuve, PodStatus

# KPI tables
from .kpi import KpiDefinition, KpiJournalier, KpiMensuel, KpiStatus, KpiDirection, KpiFrequence

# Auth
from .user import User
from .notification import NotificationLog
from .rental_approval import RentalApproval

# Legacy — kept so existing routes that import them don't break until migrated
from .ingestion_log import IngestionLog

__all__ = [
    "Camion", "CamionType", "CamionStatus",
    "Chauffeur", "PermisType", "ChauffeurStatus",
    "Client",
    "DemandeLocal", "StatutDemande", "Priorite",
    "PlanVersion", "PlanMission", "MissionDemande", "PlanningChangeLog",
    "StatutPlan", "StatutMission", "ModeMission", "Periode",
    "EvenementAlea", "EvenementType",
    "LivraisonPreuve", "PodStatus",
    "KpiDefinition", "KpiJournalier", "KpiMensuel", "KpiStatus", "KpiDirection", "KpiFrequence",
    "User",
    "NotificationLog",
    "RentalApproval",
    "IngestionLog",
]
