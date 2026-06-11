"""Real-time mission monitor.

The scheduler calls ``run()`` every 30 seconds. Tests may pass an existing
session so the job participates in the test transaction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.demande import StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.plan import MissionDemande, PlanMission, StatutMission
from app.services.incident_service import IncidentService

log = logging.getLogger(__name__)

SLA_TOLERANCE_MIN = 15


def run(db: Session | None = None, now: datetime | None = None) -> int:
    owns_session = db is None
    db = db or SessionLocal()
    now = now or datetime.now(timezone.utc)
    created = 0

    try:
        missions = (
            db.query(PlanMission)
            .filter(PlanMission.statut == StatutMission.EN_COURS)
            .all()
        )
        for mission in missions:
            created += check_mission(db, mission, now)
        if created:
            log.warning("[monitor] created %s auto incidents", created)
        else:
            log.debug("monitor tick")
        return created
    finally:
        if owns_session:
            db.close()


def check_mission(db: Session, mission: PlanMission, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    stops = sorted(mission.mission_demandes, key=lambda stop: (stop.ordre_livraison, stop.id))

    for stop in stops:
        demande = stop.demande
        if demande is None:
            continue
        if _status_value(demande.statut) in {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}:
            continue
        if _status_value(stop.statut) in {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}:
            continue
        if not stop.eta_prevue:
            continue
        if stop.eta_prevue + timedelta(minutes=SLA_TOLERANCE_MIN) >= now:
            continue
        if already_flagged(db, mission.id, stop.demande_id, now):
            return 0

        delay_min = int((now - stop.eta_prevue).total_seconds() // 60)
        IncidentService(db).log(
            type=EvenementType.RETARD_TRAFIC,
            description=(
                f"ETA missed by {delay_min} min for mission {mission.id}, "
                f"stop {stop.ordre_livraison}"
            ),
            mission_id=mission.id,
            demande_id=stop.demande_id,
            impact_delai_min=delay_min,
            cause="monitor",
        )
        return 1

    return 0


def already_flagged(db: Session, mission_id: int, demande_id: int | None, now: datetime | None = None) -> bool:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=2)
    query = db.query(EvenementAlea).filter(
        EvenementAlea.type == EvenementType.RETARD_TRAFIC,
        EvenementAlea.date_evenement > cutoff,
        EvenementAlea.mission_id == mission_id,
    )
    if demande_id is not None:
        query = query.filter(EvenementAlea.demande_id == demande_id)
    return query.count() > 0


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
