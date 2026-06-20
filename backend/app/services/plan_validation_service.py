"""Validation workflow for the Coficab PlanVersion ERD."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.kpi import KpiDefinition
from app.models.plan import MissionDemande, ModeMission, PlanMission, PlanVersion, PlanningChangeLog, StatutPlan
from app.services.dispatch_service import DispatchService
from app.services.kpi_service import compute_color


class PlanValidationService:
    def __init__(self, db: Session):
        self.db = db

    def preview_impact(self, plan_version_id: int) -> dict:
        plan = self._get_plan(plan_version_id)
        missions = plan.missions

        total_km = sum(float(m.km_parcourus or 0) for m in missions)
        total_kg = sum(float(m.charge_kg or 0) for m in missions)
        load_values = [float(m.load_eff_pct or 0) for m in missions if m.load_eff_pct is not None]
        load_eff = round(sum(load_values) / len(load_values), 2) if load_values else 0.0
        premium_cost = sum(float(m.cout_premium_eur or 0) for m in missions)
        premium_count = sum(1 for m in missions if m.mode == ModeMission.PREMIUM)
        expected_otd = self._expected_otd(missions)
        expected_fuel = self._expected_fuel(missions)

        return {
            "plan_version_id": plan.id,
            "total_km": round(total_km, 2),
            "total_kg": round(total_kg, 2),
            "load_efficiency_pct": load_eff,
            "expected_otd_pct": expected_otd,
            "expected_fuel_ml_per_tkm": expected_fuel,
            "premium_freight_count": premium_count,
            "premium_freight_eur": round(premium_cost, 2),
            "colors": {
                "otd": self._color("R4-02", expected_otd),
                "fuel": self._color("R4-13", expected_fuel),
                "load": self._color("R4", load_eff),
                "premium_eur": self._color("R4-02-PF", premium_cost),
            },
        }

    def validate(self, plan_version_id: int, username: str) -> dict:
        plan = self._get_plan(plan_version_id)
        if plan.statut_plan == StatutPlan.VALIDE:
            return {
                "plan_version_id": plan.id,
                "status": plan.statut_plan.value,
                "already_validated": True,
                "dispatch": {"sent": 0, "failed": 0, "skipped": 0},
            }
        if plan.statut_plan not in (StatutPlan.DRAFT, StatutPlan.EN_REVUE):
            raise ValueError(f"plan status {plan.statut_plan.value} cannot be validated")

        old_status = plan.statut_plan.value
        plan.statut_plan = StatutPlan.VALIDE
        plan.date_validation = datetime.now(timezone.utc)
        plan.valide_par = username
        self.db.add(
            PlanningChangeLog(
                plan_version_id=plan.id,
                field_changed="statut_plan",
                old_value=old_status,
                new_value=StatutPlan.VALIDE.value,
                reason_category="validation",
                reason_text="Plan validated by transport manager",
            )
        )
        self.db.commit()
        self.db.refresh(plan)

        dispatch_result = DispatchService(self.db).dispatch_plan(plan)
        return {
            "plan_version_id": plan.id,
            "status": plan.statut_plan.value,
            "already_validated": False,
            "dispatch": dispatch_result,
        }

    def reassign_demande(
        self,
        plan_version_id: int,
        demande_id: int,
        target_mission_id: int,
        reason: str,
        username: str,
    ) -> dict:
        plan = self._get_plan(plan_version_id)
        if plan.statut_plan == StatutPlan.VALIDE:
            raise ValueError("plan is validated; clone it before editing")
        if plan.statut_plan not in (StatutPlan.DRAFT, StatutPlan.EN_REVUE):
            raise ValueError(f"plan status {plan.statut_plan.value} cannot be edited")

        target = self.db.get(PlanMission, target_mission_id)
        if target is None or target.plan_version_id != plan.id:
            raise ValueError(f"target mission not found in plan: {target_mission_id}")

        stop = (
            self.db.query(MissionDemande)
            .join(PlanMission)
            .filter(
                MissionDemande.demande_id == demande_id,
                PlanMission.plan_version_id == plan.id,
            )
            .first()
        )
        if stop is None:
            raise ValueError(f"demande not found in plan: {demande_id}")

        old_mission_id = stop.mission_id
        if old_mission_id != target_mission_id:
            stop.mission_id = target_mission_id
            self._renumber(old_mission_id)
            self._renumber(target_mission_id)
        if plan.statut_plan == StatutPlan.DRAFT:
            plan.statut_plan = StatutPlan.EN_REVUE

        self.db.add(
            PlanningChangeLog(
                plan_version_id=plan.id,
                field_changed="mission_id",
                old_value=str(old_mission_id),
                new_value=str(target_mission_id),
                reason_category="manual_edit",
                reason_text=reason,
            )
        )
        self.db.commit()
        return {
            "plan_version_id": plan.id,
            "demande_id": demande_id,
            "old_mission_id": old_mission_id,
            "new_mission_id": target_mission_id,
            "status": plan.statut_plan.value,
            "edited_by": username,
        }

    def clone(self, plan_version_id: int, username: str) -> dict:
        source = self._get_plan(plan_version_id)
        next_version = (source.version_number or 0) + 1
        clone = PlanVersion(
            plan_id=source.plan_id,
            version_number=next_version,
            periode=source.periode,
            date_debut=source.date_debut,
            date_fin=source.date_fin,
            statut_plan=StatutPlan.DRAFT,
            commentaire=f"Cloned from PlanVersion #{source.id}",
        )
        self.db.add(clone)
        self.db.flush()

        mission_map: dict[int, PlanMission] = {}
        for mission in source.missions:
            copied = PlanMission(
                plan_version_id=clone.id,
                camion_id=mission.camion_id,
                chauffeur_id=mission.chauffeur_id,
                date_mission=mission.date_mission,
                heure_sortie_prevue=mission.heure_sortie_prevue,
                heure_retour_prevue=mission.heure_retour_prevue,
                statut=mission.statut,
                mode=mission.mode,
                km_parcourus=mission.km_parcourus,
                km_a_vide=mission.km_a_vide,
                charge_kg=mission.charge_kg,
                charge_palettes=mission.charge_palettes,
                fuel_consomme_l=mission.fuel_consomme_l,
                cout_consommables_eur=mission.cout_consommables_eur,
                cout_emballage_eur=mission.cout_emballage_eur,
                cout_transport_eur=mission.cout_transport_eur,
                cout_premium_eur=mission.cout_premium_eur,
                load_eff_kg_pct=mission.load_eff_kg_pct,
                load_eff_pallets_pct=mission.load_eff_pallets_pct,
                load_eff_pct=mission.load_eff_pct,
            )
            self.db.add(copied)
            self.db.flush()
            mission_map[mission.id] = copied
            for stop in mission.mission_demandes:
                self.db.add(
                    MissionDemande(
                        mission_id=copied.id,
                        demande_id=stop.demande_id,
                        ordre_livraison=stop.ordre_livraison,
                        eta_prevue=stop.eta_prevue,
                        eta_reelle=stop.eta_reelle,
                        statut=stop.statut,
                    )
                )

        self.db.add(
            PlanningChangeLog(
                plan_version_id=clone.id,
                field_changed="plan_version_id",
                old_value=str(source.id),
                new_value=str(clone.id),
                reason_category="clone",
                reason_text=f"Cloned by {username}",
            )
        )
        self.db.commit()
        self.db.refresh(clone)
        return {
            "source_plan_version_id": source.id,
            "plan_version_id": clone.id,
            "status": clone.statut_plan.value,
            "version_number": clone.version_number,
            "missions": len(mission_map),
        }

    def changelog(self, plan_version_id: int) -> list[dict]:
        self._get_plan(plan_version_id)
        rows = (
            self.db.query(PlanningChangeLog)
            .filter(PlanningChangeLog.plan_version_id == plan_version_id)
            .order_by(PlanningChangeLog.timestamp.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "plan_version_id": row.plan_version_id,
                "field_changed": row.field_changed,
                "old_value": row.old_value,
                "new_value": row.new_value,
                "reason_category": row.reason_category,
                "reason_text": row.reason_text,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            for row in rows
        ]

    def _get_plan(self, plan_version_id: int) -> PlanVersion:
        plan = self.db.get(PlanVersion, plan_version_id)
        if plan is None:
            raise ValueError(f"plan version not found: {plan_version_id}")
        return plan

    def _renumber(self, mission_id: int) -> None:
        stops = (
            self.db.query(MissionDemande)
            .filter(MissionDemande.mission_id == mission_id)
            .order_by(MissionDemande.ordre_livraison, MissionDemande.id)
            .all()
        )
        for index, stop in enumerate(stops, start=1):
            stop.ordre_livraison = index

    def _color(self, code: str, value: float | None) -> str:
        definition = self.db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
        if definition is None or value is None:
            return "grey"
        return compute_color(definition, value)

    @staticmethod
    def _expected_otd(missions) -> float:
        total = 0
        on_time = 0
        for mission in missions:
            for stop in mission.mission_demandes:
                total += 1
                demande = stop.demande
                if demande and demande.heure_arrivee_prevue and stop.eta_prevue:
                    if stop.eta_prevue <= demande.heure_arrivee_prevue:
                        on_time += 1
        return round((on_time / total * 100), 2) if total else 0.0

    @staticmethod
    def _expected_fuel(missions) -> float:
        fuel = sum(float(m.fuel_consomme_l or 0) for m in missions)
        kg = sum(float(m.charge_kg or 0) for m in missions)
        km = sum(float(m.km_parcourus or 0) for m in missions)
        if not fuel or not kg or not km:
            return 0.0
        return round(fuel * 1000 / ((kg / 1000) * km), 4)
