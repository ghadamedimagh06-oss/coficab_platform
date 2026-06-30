from datetime import date, datetime

from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.kpi import KpiDefinition, KpiDirection, KpiFrequence
from app.models.notification import NotificationLog
from app.models.plan import MissionDemande, Periode, PlanMission, PlanVersion, StatutPlan


def _seed_kpi_definitions(db):
    db.add_all(
        [
            KpiDefinition(code="R4-02", nom="OTD", unite="%", frequence=KpiFrequence.monthly, direction=KpiDirection.UP, green_min=94, yellow_min=92),
            KpiDefinition(code="R4-13", nom="Fuel", unite="mL/T.km", frequence=KpiFrequence.monthly, direction=KpiDirection.DOWN, green_max=160, yellow_max=180),
            KpiDefinition(code="R4", nom="Load", unite="%", frequence=KpiFrequence.daily, direction=KpiDirection.UP, green_min=80, yellow_min=70),
            KpiDefinition(code="R4-02-PF", nom="Premium", unite="EUR", frequence=KpiFrequence.monthly, direction=KpiDirection.DOWN, green_max=2500, yellow_max=3500),
        ]
    )


def _seed_plan(db, two_missions=False):
    target = date(2026, 5, 22)
    client = Client(id=901, nom="Validation Client", city="Sfax")
    camion = Camion(
        plate_number="VAL-001",
        type=CamionType.SEMI,
        capacite_kg=10000,
        max_palettes=20,
        status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=9901,
        full_name="Validation Driver",
        phone="+21650000001",
        permis_type=PermisType.CE,
        status=ChauffeurStatus.ACTIF,
    )
    plan = PlanVersion(
        plan_id=9901,
        version_number=1,
        periode=Periode.JOUR,
        date_debut=target,
        date_fin=target,
        statut_plan=StatutPlan.DRAFT,
    )
    db.add_all([client, camion, chauffeur, plan])
    db.flush()
    demande = DemandeLocal(
        client_id=client.id,
        quantite_kg=2500,
        nombre_palettes=4,
        date_livraison=target,
        heure_arrivee_prevue=datetime(2026, 5, 22, 10, 0),
        statut=StatutDemande.PLANIFIEE,
        priorite=Priorite.NORMALE,
    )
    mission = PlanMission(
        plan_version_id=plan.id,
        camion_id=camion.id,
        chauffeur_id=chauffeur.id,
        date_mission=target,
        km_parcourus=100,
        charge_kg=2500,
        fuel_consomme_l=0.04,
        load_eff_pct=75,
    )
    db.add_all([demande, mission])
    db.flush()
    db.add(
        MissionDemande(
            mission_id=mission.id,
            demande_id=demande.id,
            ordre_livraison=1,
            eta_prevue=datetime(2026, 5, 22, 9, 30),
        )
    )
    if two_missions:
        demande_2 = DemandeLocal(
            client_id=client.id,
            quantite_kg=1200,
            nombre_palettes=2,
            date_livraison=target,
            statut=StatutDemande.PLANIFIEE,
            priorite=Priorite.NORMALE,
        )
        mission_2 = PlanMission(
            plan_version_id=plan.id,
            camion_id=camion.id,
            chauffeur_id=chauffeur.id,
            date_mission=target,
            km_parcourus=50,
            charge_kg=1200,
            fuel_consomme_l=0.02,
            load_eff_pct=40,
        )
        db.add_all([demande_2, mission_2])
        db.flush()
        db.add(
            MissionDemande(
                mission_id=mission_2.id,
                demande_id=demande_2.id,
                ordre_livraison=1,
                eta_prevue=datetime(2026, 5, 22, 11, 0),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def test_plan_version_impact_validate_dispatch_and_changelog(client, db):
    _seed_kpi_definitions(db)
    plan = _seed_plan(db)

    impact = client.get(f"/api/planning/{plan.id}/impact")
    assert impact.status_code == 200, impact.text
    impact_json = impact.json()
    assert impact_json["expected_otd_pct"] == 100.0
    assert impact_json["load_efficiency_pct"] == 75.0
    assert impact_json["colors"]["load"] == "yellow"

    validated = client.post(f"/api/planning/{plan.id}/validate")
    assert validated.status_code == 200, validated.text
    assert validated.json()["status"] == "VALIDE"
    assert validated.json()["dispatch"]["sent"] == 1
    assert db.get(PlanVersion, plan.id).statut_plan == StatutPlan.VALIDE
    assert db.query(NotificationLog).count() == 1

    repeated = client.post(f"/api/planning/{plan.id}/validate")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["already_validated"] is True
    assert db.query(NotificationLog).count() == 1

    changelog = client.get(f"/api/planning/{plan.id}/changelog")
    assert changelog.status_code == 200, changelog.text
    assert changelog.json()["changelog"][0]["field_changed"] == "statut_plan"


def test_plan_version_reassign_and_clone_validated_plan(client, db):
    plan = _seed_plan(db, two_missions=True)
    missions = sorted(plan.missions, key=lambda item: item.id)
    stop = missions[0].mission_demandes[0]
    target_mission = missions[1]

    moved = client.post(
        f"/api/planning/{plan.id}/reassign",
        json={
            "demande_id": stop.demande_id,
            "target_mission_id": target_mission.id,
            "reason": "balance load",
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "EN_REVUE"
    db.refresh(stop)
    assert stop.mission_id == target_mission.id

    validated = client.post(f"/api/planning/{plan.id}/validate")
    assert validated.status_code == 200, validated.text

    blocked = client.post(
        f"/api/planning/{plan.id}/reassign",
        json={
            "demande_id": stop.demande_id,
            "target_mission_id": missions[0].id,
            "reason": "late change",
        },
    )
    assert blocked.status_code == 409

    cloned = client.post(f"/api/planning/{plan.id}/clone")
    assert cloned.status_code == 200, cloned.text
    clone_id = cloned.json()["plan_version_id"]
    cloned_plan = db.get(PlanVersion, clone_id)
    assert cloned_plan.statut_plan == StatutPlan.DRAFT
    assert len(cloned_plan.missions) == 2
    assert sum(len(mission.mission_demandes) for mission in cloned_plan.missions) == 2
