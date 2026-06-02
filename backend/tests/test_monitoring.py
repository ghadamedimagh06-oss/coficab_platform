from datetime import date, datetime, timedelta

from app.agents.monitor import run
from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.plan import MissionDemande, Periode, PlanMission, PlanVersion, StatutMission


def _seed_mission(db, *, eta: datetime, statut=StatutMission.EN_COURS):
    target = eta.date() or date.today()
    client = Client(id=1701, nom="Tracking Client", city="Tunis")
    camion = Camion(
        plate_number=f"TRK-{eta.hour}-{eta.minute}",
        type=CamionType.SEMI,
        capacite_kg=12000,
        max_palettes=24,
        status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=11701,
        full_name="Tracking Driver",
        permis_type=PermisType.CE,
        status=ChauffeurStatus.ACTIF,
    )
    plan = PlanVersion(
        plan_id=11701,
        version_number=1,
        periode=Periode.JOUR,
        date_debut=target,
        date_fin=target,
    )
    db.add_all([client, camion, chauffeur, plan])
    db.flush()

    demande = DemandeLocal(
        client_id=client.id,
        quantite_kg=900,
        date_livraison=target,
        statut=StatutDemande.PLANIFIEE,
        priorite=Priorite.NORMALE,
    )
    mission = PlanMission(
        plan_version_id=plan.id,
        camion_id=camion.id,
        chauffeur_id=chauffeur.id,
        date_mission=target,
        statut=statut,
    )
    db.add_all([demande, mission])
    db.flush()

    stop = MissionDemande(
        mission_id=mission.id,
        demande_id=demande.id,
        ordre_livraison=1,
        eta_prevue=eta,
        statut=StatutDemande.PLANIFIEE.value,
    )
    db.add(stop)
    db.commit()
    db.refresh(mission)
    db.refresh(stop)
    db.refresh(demande)
    return mission, stop, demande


def test_monitor_logs_eta_missed_incident_once(db):
    now = datetime.utcnow()
    mission, stop, _demande = _seed_mission(db, eta=now - timedelta(minutes=40))

    assert run(db=db, now=now) == 1

    incident = db.query(EvenementAlea).one()
    assert incident.type == EvenementType.RETARD_TRAFIC
    assert incident.mission_id == mission.id
    assert incident.demande_id == stop.demande_id
    assert incident.impact_delai_min == 40
    assert incident.cause == "monitor"

    assert run(db=db, now=now) == 0
    assert db.query(EvenementAlea).count() == 1


def test_stop_delivered_endpoint_updates_demande_and_closes_mission(client, db):
    mission, stop, demande = _seed_mission(db, eta=datetime.utcnow() + timedelta(hours=1))

    response = client.post(
        f"/api/tracking/stops/{stop.id}/delivered",
        json={"quantite_livree_kg": 875},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["on_time"] is True
    assert payload["mission_status"] == StatutMission.TERMINEE.value

    db.expire_all()
    delivered = db.get(DemandeLocal, demande.id)
    assert delivered.statut == StatutDemande.LIVREE
    assert float(delivered.quantite_livree_kg) == 875
    assert delivered.livree_a_temps is True

    closed_mission = db.get(PlanMission, mission.id)
    assert closed_mission.statut == StatutMission.TERMINEE
    assert closed_mission.heure_retour_reelle is not None

    status = client.get(f"/api/tracking/missions/{mission.id}/status")
    assert status.status_code == 200, status.text
    status_payload = status.json()
    assert status_payload["current_stop_id"] is None
    assert status_payload["delivered_count"] == 1
    assert status_payload["stops"][0]["statut"] == StatutDemande.LIVREE.value
