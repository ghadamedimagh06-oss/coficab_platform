"""Driver dispatch and notification orchestration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.notification import NotificationLog
from app.models.plan import PlanMission, PlanVersion
from app.providers.notification import MockProvider, NotificationProvider


class DispatchService:
    def __init__(self, db: Session, provider: NotificationProvider | None = None):
        self.db = db
        self.provider = provider or MockProvider()

    def dispatch_plan(self, plan: PlanVersion) -> dict:
        sent = failed = skipped = 0
        for mission in sorted(plan.missions, key=lambda item: item.id):
            status = self.dispatch_mission(mission)
            if status == "sent":
                sent += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
        return {"sent": sent, "failed": failed, "skipped": skipped}

    def dispatch_mission(self, mission: PlanMission) -> str:
        driver = mission.chauffeur
        if not driver or not driver.phone:
            self._log_attempt(mission, "skipped", "no phone", None)
            return "skipped"

        brief = self.build_brief(mission)
        try:
            self.provider.send(driver.phone, brief)
        except Exception as exc:
            self._log_attempt(mission, "failed", str(exc), brief)
            return "failed"

        self._log_attempt(mission, "sent", None, brief)
        return "sent"

    def build_brief(self, mission: PlanMission) -> str:
        lines = [
            f"COFICAB - Mission #{mission.id}",
            f"Date: {mission.date_mission}",
        ]
        if mission.camion:
            truck_type = mission.camion.type.value if hasattr(mission.camion.type, "value") else mission.camion.type
            lines.append(f"Camion: {mission.camion.plate_number} ({truck_type})")
        if mission.heure_sortie_prevue:
            lines.append(f"Depart: {mission.heure_sortie_prevue.strftime('%H:%M')}")
        lines.append("")

        stops = sorted(mission.mission_demandes, key=lambda stop: stop.ordre_livraison)
        for stop in stops:
            demande = stop.demande
            client = demande.client if demande else None
            client_name = client.nom if client else f"Demande {stop.demande_id}"
            city = f" {client.city}" if client and client.city else ""
            eta = stop.eta_prevue.strftime("%H:%M") if stop.eta_prevue else "--"
            kg = int(demande.quantite_kg or 0) if demande else 0
            palettes = demande.nombre_palettes or 0 if demande else 0
            lines.append(f"Stop {stop.ordre_livraison} - {client_name}{city}")
            lines.append(f"  ETA {eta} - {kg} kg - {palettes} palettes")
            if client and client.numero:
                lines.append(f"  Contact: {client.numero}")
            lines.append("")

        if mission.heure_retour_prevue:
            lines.append(f"Retour: {mission.heure_retour_prevue.strftime('%H:%M')}")
        lines.append("Confirmer: repondez OK")
        return "\n".join(lines)

    def _log_attempt(self, mission: PlanMission, status: str, error: str | None, body: str | None) -> None:
        self.db.add(
            NotificationLog(
                mission_id=mission.id,
                chauffeur_id=mission.chauffeur_id,
                status=status,
                error=error,
                body=body,
                sent_at=datetime.utcnow(),
            )
        )
        self.db.commit()
