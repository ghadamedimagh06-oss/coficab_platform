from datetime import date, datetime

from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.notification import NotificationLog
from app.models.plan import MissionDemande, Periode, PlanMission, PlanVersion
from app.services.dispatch_service import DispatchService


def _seed_mission(db, *, phone="+21650000000"):
    target = date(2026, 5, 21)
    client = Client(id=801, nom="Dispatch Client", city="Tunis", numero="+21671111111")
    camion = Camion(
        plate_number="DSP-001",
        type=CamionType.SEMI,
        capacite_kg=12000,
        max_palettes=24,
        status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=8801,
        full_name="Dispatch Driver",
        phone=phone,
        permis_type=PermisType.CE,
        status=ChauffeurStatus.ACTIF,
    )
    plan = PlanVersion(
        plan_id=8801,
        version_number=1,
        periode=Periode.JOUR,
        date_debut=target,
        date_fin=target,
    )
    db.add_all([client, camion, chauffeur, plan])
    db.flush()
    demande = DemandeLocal(
        client_id=client.id,
        quantite_kg=1500,
        nombre_palettes=3,
        date_livraison=target,
        statut=StatutDemande.PLANIFIEE,
        priorite=Priorite.NORMALE,
    )
    mission = PlanMission(
        plan_version_id=plan.id,
        camion_id=camion.id,
        chauffeur_id=chauffeur.id,
        date_mission=target,
        heure_sortie_prevue=datetime(2026, 5, 21, 8, 0),
        heure_retour_prevue=datetime(2026, 5, 21, 12, 0),
    )
    db.add_all([demande, mission])
    db.flush()
    db.add(
        MissionDemande(
            mission_id=mission.id,
            demande_id=demande.id,
            ordre_livraison=1,
            eta_prevue=datetime(2026, 5, 21, 9, 30),
        )
    )
    db.commit()
    db.refresh(mission)
    db.refresh(plan)
    return plan, mission


def test_dispatch_service_builds_brief_and_logs_sent(db):
    _plan, mission = _seed_mission(db)
    service = DispatchService(db)

    brief = service.build_brief(mission)
    assert "COFICAB - Mission" in brief
    assert "Dispatch Client Tunis" in brief
    assert "ETA 09:30" in brief

    assert service.dispatch_mission(mission) == "sent"
    log = db.query(NotificationLog).one()
    assert log.status == "sent"
    assert "Dispatch Client" in log.body


def test_dispatch_service_logs_skipped_without_phone(db):
    _plan, mission = _seed_mission(db, phone=None)

    assert DispatchService(db).dispatch_mission(mission) == "skipped"
    log = db.query(NotificationLog).one()
    assert log.status == "skipped"
    assert log.error == "no phone"


def test_dispatch_routes_preview_resend_plan_and_logs(client, db):
    plan, mission = _seed_mission(db)

    brief = client.get(f"/api/dispatch/missions/{mission.id}/brief")
    assert brief.status_code == 200, brief.text
    assert "Dispatch Client" in brief.text

    resend = client.post(f"/api/dispatch/missions/{mission.id}/resend")
    assert resend.status_code == 200, resend.text
    assert resend.json()["status"] == "sent"

    plan_send = client.post(f"/api/dispatch/plans/{plan.id}/send")
    assert plan_send.status_code == 200, plan_send.text
    assert plan_send.json()["sent"] == 1

    logs = client.get("/api/dispatch/logs")
    assert logs.status_code == 200, logs.text
    assert logs.json()["count"] == 2
    assert {row["status"] for row in logs.json()["logs"]} == {"sent"}
