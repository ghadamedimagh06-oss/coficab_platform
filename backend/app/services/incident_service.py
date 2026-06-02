"""Incident and alea tracking service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.demande import DemandeLocal, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.plan import PlanMission, StatutMission


class IncidentService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        type: EvenementType,
        description: str | None,
        mission_id: int | None = None,
        demande_id: int | None = None,
        impact_delai_min: int = 0,
        cause: str | None = None,
    ) -> EvenementAlea:
        plan_version_id = None
        if mission_id is not None:
            mission = self.db.get(PlanMission, mission_id)
            if mission is None:
                raise ValueError(f"mission not found: {mission_id}")
            plan_version_id = mission.plan_version_id

        if demande_id is not None and self.db.get(DemandeLocal, demande_id) is None:
            raise ValueError(f"demande not found: {demande_id}")

        incident = EvenementAlea(
            plan_version_id=plan_version_id,
            mission_id=mission_id,
            demande_id=demande_id,
            type=type,
            description=description,
            impact_delai_min=impact_delai_min or 0,
            cause=cause,
            date_evenement=datetime.utcnow(),
        )
        self.db.add(incident)
        self._apply_side_effects(type, mission_id, demande_id)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def resolve(self, incident_id: int, note: str | None = None) -> EvenementAlea:
        incident = self.db.get(EvenementAlea, incident_id)
        if incident is None:
            raise ValueError(f"incident not found: {incident_id}")

        incident.resolu = True
        incident.date_resolution = datetime.utcnow()
        if note:
            incident.description = f"{incident.description or ''}\nRESOLU: {note}".strip()
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def _apply_side_effects(
        self,
        type: EvenementType,
        mission_id: int | None,
        demande_id: int | None,
    ) -> None:
        if type == EvenementType.PANNE_VEHICULE and mission_id is not None:
            mission = self.db.get(PlanMission, mission_id)
            if mission is not None:
                mission.statut = StatutMission.ANNULEE
        elif type == EvenementType.CLIENT_INDISPONIBLE and demande_id is not None:
            demande = self.db.get(DemandeLocal, demande_id)
            if demande is not None:
                demande.statut = StatutDemande.ANNULEE
