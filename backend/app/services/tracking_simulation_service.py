"""Deterministic map replay for delay demonstrations.

This service is deliberately isolated from the real TFM ingestion path. Every
sample it creates is tagged ``MAP_SIMULATION`` so demo data cannot be mistaken
for production telemetry.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agents.monitor import SLA_TOLERANCE_MIN, already_flagged
from app.models.demande import StatutDemande
from app.models.evenement import EvenementType
from app.models.plan import PlanMission
from app.models.transport_tracking import TransportTracking
from app.services.geo_service import GeoService
from app.services.incident_service import IncidentService


class TrackingSimulationService:
    SOURCE = "MAP_SIMULATION"

    def __init__(self, db: Session):
        self.db = db

    def run(
        self,
        mission_id: int,
        *,
        progress_pct: float = 50,
        delay_minutes: int = 0,
        now: datetime | None = None,
    ) -> dict:
        mission = self.db.get(PlanMission, mission_id)
        if mission is None:
            raise ValueError("mission not found")
        from app.models.plan import StatutMission
        if mission.statut != StatutMission.EN_COURS:
            raise ValueError("map delay simulation requires an EN_COURS mission")
        progress = max(0.0, min(100.0, float(progress_pct))) / 100
        now = now or datetime.utcnow()
        stop = self._next_stop(mission)
        if stop is None or stop.demande is None or stop.demande.client is None:
            raise ValueError("mission has no pending stop")
        client = stop.demande.client
        if client.latitude is None or client.longitude is None:
            raise ValueError("pending stop client has no map coordinates")

        depot_lat, depot_lon = GeoService().depot()
        target_lat = float(client.latitude)
        target_lon = float(client.longitude)
        location = {
            "lat": round(depot_lat + (target_lat - depot_lat) * progress, 6),
            "lng": round(depot_lon + (target_lon - depot_lon) * progress, 6),
        }
        delayed = delay_minutes > SLA_TOLERANCE_MIN
        expected_eta = stop.eta_prevue or now
        simulated_eta = expected_eta + timedelta(minutes=delay_minutes)
        tracking = TransportTracking(
            transport_id=f"mission-{mission.id}",
            status="delayed" if delayed else "on_time",
            location=json.dumps(location),
            eta_hours=max(0, (simulated_eta - now).total_seconds() / 3600),
            distance_remaining=None,
            source=self.SOURCE,
            timestamp=now,
        )
        self.db.add(tracking)
        self.db.flush()

        incident = None
        if delayed and not already_flagged(self.db, mission.id, stop.demande_id, now):
            incident = IncidentService(self.db).log(
                type=EvenementType.RETARD_TRAFIC,
                description=(
                    f"Map simulation: mission {mission.id} is delayed by "
                    f"{delay_minutes} minutes at stop {stop.ordre_livraison}"
                ),
                mission_id=mission.id,
                demande_id=stop.demande_id,
                impact_delai_min=delay_minutes,
                cause=self.SOURCE,
            )
        else:
            self.db.commit()
        self.db.refresh(tracking)
        return {
            "tracking": {
                "id": tracking.id,
                "transport_id": tracking.transport_id,
                "mission_id": mission.id,
                "status": tracking.status,
                "location": location,
                "eta_hours": tracking.eta_hours,
                "source": tracking.source,
                "timestamp": tracking.timestamp.isoformat() if tracking.timestamp else None,
            },
            "incident": (
                {
                    "id": incident.id,
                    "type": incident.type.value,
                    "impact_delai_min": incident.impact_delai_min,
                    "source": incident.cause,
                }
                if incident is not None
                else None
            ),
        }

    @staticmethod
    def _next_stop(mission: PlanMission):
        closed = {StatutDemande.LIVREE.value, StatutDemande.ANNULEE.value}
        return next(
            (
                stop
                for stop in sorted(
                    mission.mission_demandes,
                    key=lambda item: (item.ordre_livraison, item.id),
                )
                if (stop.statut.value if hasattr(stop.statut, "value") else str(stop.statut))
                not in closed
            ),
            None,
        )
