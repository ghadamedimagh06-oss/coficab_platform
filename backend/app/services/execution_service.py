"""
Execution & ePOD service — the P0 "execution loop" (docs/TMS_ROADMAP.md §4/§5).

Turns a persisted DRAFT plan into executed, delivery-confirmed actuals:

    DRAFT ─validate→ VALIDE ─start→ EXECUTE ─(all delivered)→ CLOTURE
                              │
        PlanMission:  PLANIFIEE ─start→ EN_COURS ─(stops done)→ TERMINEE
        DemandeLocal: PLANIFIEE ─start→ EN_COURS ─confirm→ LIVREE  (or ANNULEE)

Confirming a delivery (ePOD) writes quantite_livree_kg / livree_a_temps /
heure_arrivee_reelle on the DemandeLocal — exactly the fields KpiService's OTIF
and OTD live computers read — and stores a LivraisonPreuve proof record.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.camion import Camion, CamionStatus
from app.models.demande import DemandeLocal, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.plan import (
    PlanVersion, PlanMission, MissionDemande,
    StatutPlan, StatutMission,
)
from app.models.proof import LivraisonPreuve, PodStatus

log = logging.getLogger(__name__)

# A delivery counts as on-time if it arrives at most this many minutes after the
# planned arrival (operational tolerance).
ON_TIME_GRACE_MINUTES = 15


class ExecutionError(Exception):
    """Raised for invalid state transitions; mapped to HTTP 409 by the route."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Drop tzinfo so naive (seed) and aware datetimes can be compared."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ reads
    def get_plan(self, plan_version_id: int) -> PlanVersion:
        plan = self.db.get(PlanVersion, plan_version_id)
        if plan is None:
            raise ExecutionError(f"plan version {plan_version_id} not found")
        return plan

    def get_mission(self, mission_id: int) -> PlanMission:
        mission = self.db.get(PlanMission, mission_id)
        if mission is None:
            raise ExecutionError(f"mission {mission_id} not found")
        return mission

    # ------------------------------------------------------------ transitions
    def validate_plan(self, plan_version_id: int, user: str) -> PlanVersion:
        plan = self.get_plan(plan_version_id)
        if plan.statut_plan not in (StatutPlan.DRAFT, StatutPlan.EN_REVUE):
            raise ExecutionError(
                f"plan {plan_version_id} is {plan.statut_plan}; only DRAFT/EN_REVUE can be validated"
            )
        plan.statut_plan = StatutPlan.VALIDE
        plan.date_validation = _now()
        plan.valide_par = user
        self.db.commit()
        return plan

    def start_plan(self, plan_version_id: int) -> PlanVersion:
        """Move a VALIDE/DRAFT plan into EXECUTE and start all its missions."""
        plan = self.get_plan(plan_version_id)
        if plan.statut_plan in (StatutPlan.EXECUTE, StatutPlan.CLOTURE):
            raise ExecutionError(f"plan {plan_version_id} already {plan.statut_plan}")
        for mission in plan.missions:
            if mission.statut == StatutMission.PLANIFIEE:
                self._start_mission(mission)
        plan.statut_plan = StatutPlan.EXECUTE
        self.db.commit()
        return plan

    def start_mission(self, mission_id: int) -> PlanMission:
        mission = self.get_mission(mission_id)
        if mission.statut != StatutMission.PLANIFIEE:
            raise ExecutionError(f"mission {mission_id} is {mission.statut}; expected PLANIFIEE")
        self._start_mission(mission)
        # Ensure the parent plan reflects that execution has begun.
        plan = self.db.get(PlanVersion, mission.plan_version_id)
        if plan and plan.statut_plan in (StatutPlan.DRAFT, StatutPlan.EN_REVUE, StatutPlan.VALIDE):
            plan.statut_plan = StatutPlan.EXECUTE
        self.db.commit()
        return mission

    def _start_mission(self, mission: PlanMission) -> None:
        mission.statut = StatutMission.EN_COURS
        mission.heure_sortie_reelle = _now()
        camion = self.db.get(Camion, mission.camion_id)
        if camion is not None:
            camion.status = CamionStatus.EN_MISSION
        for md in mission.mission_demandes:
            if md.statut in ("PLANIFIEE", StatutDemande.PLANIFIEE):
                md.statut = "EN_COURS"
            if md.demande and md.demande.statut == StatutDemande.PLANIFIEE:
                md.demande.statut = StatutDemande.EN_COURS

    # --------------------------------------------------------------- ePOD
    def confirm_delivery(
        self,
        mission_demande_id: int,
        *,
        quantite_livree_kg: Optional[float] = None,
        delivered_at: Optional[datetime] = None,
        on_time: Optional[bool] = None,
        signataire: Optional[str] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> LivraisonPreuve:
        """Record proof of delivery for one stop and advance its demande to LIVREE."""
        md = self.db.get(MissionDemande, mission_demande_id)
        if md is None:
            raise ExecutionError(f"mission_demande {mission_demande_id} not found")
        if str(md.statut) == "LIVREE":
            raise ExecutionError(f"stop {mission_demande_id} already delivered")
        demande = md.demande
        if demande is None:
            raise ExecutionError(f"stop {mission_demande_id} has no linked demande")

        delivered_at = delivered_at or _now()
        ordered_kg = float(demande.quantite_kg or 0)
        delivered_kg = float(quantite_livree_kg) if quantite_livree_kg is not None else ordered_kg

        if on_time is None:
            on_time = self._is_on_time(demande, md, delivered_at)

        in_full = delivered_kg + 1e-6 >= ordered_kg and ordered_kg > 0
        pod_status = PodStatus.LIVREE if in_full else PodStatus.PARTIELLE

        # Update the demande — the source of truth for OTIF/OTD.
        demande.statut = StatutDemande.LIVREE
        demande.heure_arrivee_reelle = delivered_at
        demande.quantite_livree_kg = delivered_kg
        demande.livree_a_temps = bool(on_time)

        # Update the stop.
        md.statut = "LIVREE"
        md.eta_reelle = delivered_at

        proof = LivraisonPreuve(
            mission_demande_id=md.id,
            demande_id=demande.id,
            statut=pod_status,
            delivered_at=delivered_at,
            quantite_livree_kg=delivered_kg,
            on_time=bool(on_time),
            signataire=signataire,
            photo_url=photo_url,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(proof)

        self._maybe_close_mission(md.mission_id)
        self.db.commit()
        self.db.refresh(proof)
        return proof

    def report_exception(
        self,
        mission_demande_id: int,
        *,
        type: str,
        description: Optional[str] = None,
        cancel: bool = True,
        created_by: Optional[str] = None,
    ) -> EvenementAlea:
        """Capture a delivery exception (refusal, client unavailable, …).

        Logs an EvenementAlea and, when cancel=True, marks the stop/demande
        ANNULEE so it stops counting as a pending delivery. A refusal is also
        recorded as a REFUSEE proof so OTIF reflects the failed delivery.
        """
        md = self.db.get(MissionDemande, mission_demande_id)
        if md is None:
            raise ExecutionError(f"mission_demande {mission_demande_id} not found")
        try:
            ev_type = EvenementType(type)
        except ValueError:
            raise ExecutionError(
                f"unknown exception type {type!r}; expected one of "
                f"{[t.value for t in EvenementType]}"
            )
        mission = self.db.get(PlanMission, md.mission_id)
        ev = EvenementAlea(
            plan_version_id=mission.plan_version_id if mission else None,
            mission_id=md.mission_id,
            demande_id=md.demande_id,
            type=ev_type,
            description=description,
        )
        self.db.add(ev)

        if cancel:
            md.statut = "ANNULEE"
            if md.demande:
                md.demande.statut = StatutDemande.ANNULEE
            self.db.add(LivraisonPreuve(
                mission_demande_id=md.id,
                demande_id=md.demande_id,
                statut=PodStatus.REFUSEE,
                delivered_at=_now(),
                quantite_livree_kg=0,
                on_time=False,
                notes=description,
                created_by=created_by,
            ))
            self._maybe_close_mission(md.mission_id)

        self.db.commit()
        self.db.refresh(ev)
        return ev

    # ------------------------------------------------------------- internals
    def _maybe_close_mission(self, mission_id: int) -> None:
        mission = self.db.get(PlanMission, mission_id)
        if mission is None:
            return
        terminal = {"LIVREE", "ANNULEE"}
        if mission.mission_demandes and all(
            str(md.statut) in terminal for md in mission.mission_demandes
        ):
            mission.statut = StatutMission.TERMINEE
            mission.heure_retour_reelle = _now()
            camion = self.db.get(Camion, mission.camion_id)
            if camion is not None:
                camion.status = CamionStatus.DISPONIBLE
            self._maybe_close_plan(mission.plan_version_id)

    def _maybe_close_plan(self, plan_version_id: int) -> None:
        plan = self.db.get(PlanVersion, plan_version_id)
        if plan is None:
            return
        terminal = {StatutMission.TERMINEE, StatutMission.ANNULEE}
        if plan.missions and all(m.statut in terminal for m in plan.missions):
            plan.statut_plan = StatutPlan.CLOTURE

    @staticmethod
    def _is_on_time(demande: DemandeLocal, md: MissionDemande, delivered_at: datetime) -> bool:
        """On-time if delivered no later than the planned arrival + grace.

        Planned arrival is taken from the stop's eta_prevue, else the demande's
        heure_arrivee_prevue. With no planned time we cannot prove lateness, so
        we treat it as on-time.
        """
        planned = _naive(md.eta_prevue) or _naive(demande.heure_arrivee_prevue)
        if planned is None:
            return True
        delivered = _naive(delivered_at)
        delta_min = (delivered - planned).total_seconds() / 60.0
        return delta_min <= ON_TIME_GRACE_MINUTES

    # ----------------------------------------------------------------- status
    def plan_status(self, plan_version_id: int) -> dict:
        plan = self.get_plan(plan_version_id)
        missions = plan.missions
        stops = [md for m in missions for md in m.mission_demandes]
        delivered = sum(1 for s in stops if str(s.statut) == "LIVREE")
        cancelled = sum(1 for s in stops if str(s.statut) == "ANNULEE")
        pending = len(stops) - delivered - cancelled
        return {
            "plan_version_id": plan.id,
            "statut_plan": str(plan.statut_plan),
            "date": str(plan.date_debut),
            "missions_total": len(missions),
            "missions_done": sum(1 for m in missions if m.statut == StatutMission.TERMINEE),
            "stops_total": len(stops),
            "stops_delivered": delivered,
            "stops_cancelled": cancelled,
            "stops_pending": pending,
            "completion_pct": round(delivered / len(stops) * 100, 1) if stops else 0.0,
            "missions": [
                {
                    "mission_id": m.id,
                    "camion_id": m.camion_id,
                    "chauffeur_id": m.chauffeur_id,
                    "statut": str(m.statut),
                    "stops": [
                        {
                            "mission_demande_id": md.id,
                            "demande_id": md.demande_id,
                            "ordre": md.ordre_livraison,
                            "statut": str(md.statut),
                            "client": (md.demande.client.nom if md.demande and md.demande.client else None),
                            "quantite_kg": float(md.demande.quantite_kg) if md.demande and md.demande.quantite_kg else None,
                            "quantite_livree_kg": float(md.demande.quantite_livree_kg) if md.demande and md.demande.quantite_livree_kg is not None else None,
                            "livree_a_temps": md.demande.livree_a_temps if md.demande else None,
                        }
                        for md in sorted(m.mission_demandes, key=lambda x: x.ordre_livraison)
                    ],
                }
                for m in missions
            ],
        }
