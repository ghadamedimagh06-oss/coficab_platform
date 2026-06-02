from datetime import date, datetime

from app.agents.kpi_jobs import run_monthly
from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.kpi import KpiDefinition, KpiDirection, KpiFrequence, KpiMensuel, KpiStatus
from app.models.plan import Periode, PlanMission, PlanVersion, StatutMission
from app.services.incident_service import IncidentService


def _seed_demande(db, target=date(2026, 5, 20)):
    db.add(Client(id=701, nom="Incident Client"))
    db.flush()
    demande = DemandeLocal(
        client_id=701,
        quantite_kg=1000,
        date_livraison=target,
        statut=StatutDemande.PLANIFIEE,
        priorite=Priorite.NORMALE,
    )
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return demande


def _seed_mission(db, target=date(2026, 5, 20), km=100000):
    camion = Camion(
        plate_number=f"INC-{target.day}-{km}",
        type=CamionType.SEMI,
        capacite_kg=10000,
        max_palettes=20,
        status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=9000 + target.day,
        full_name="Incident Driver",
        permis_type=PermisType.CE,
        status=ChauffeurStatus.ACTIF,
    )
    version = PlanVersion(
        plan_id=9000 + target.day,
        version_number=1,
        periode=Periode.JOUR,
        date_debut=target,
        date_fin=target,
    )
    db.add_all([camion, chauffeur, version])
    db.flush()
    mission = PlanMission(
        plan_version_id=version.id,
        camion_id=camion.id,
        chauffeur_id=chauffeur.id,
        date_mission=target,
        statut=StatutMission.EN_COURS,
        km_parcourus=km,
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


def test_incident_service_logs_resolves_and_applies_side_effects(db):
    demande = _seed_demande(db)
    service = IncidentService(db)

    incident = service.log(
        type=EvenementType.CLIENT_INDISPONIBLE,
        description="Client closed",
        demande_id=demande.id,
        impact_delai_min=45,
    )

    assert incident.id is not None
    assert db.get(DemandeLocal, demande.id).statut == StatutDemande.ANNULEE

    resolved = service.resolve(incident.id, "Planner called customer")
    assert resolved.resolu is True
    assert resolved.date_resolution is not None
    assert "RESOLU" in resolved.description


def test_incident_routes_list_stats_and_resolve(client, db):
    mission = _seed_mission(db)

    created = client.post(
        "/api/incidents",
        json={
            "type": "PANNE_VEHICULE",
            "description": "Truck breakdown",
            "mission_id": mission.id,
            "impact_delai_min": 30,
            "cause": "vehicle",
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["plan_version_id"] == mission.plan_version_id
    assert db.get(PlanMission, mission.id).statut == StatutMission.ANNULEE

    listed = client.get("/api/incidents?resolu=false")
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1

    month = payload["date_evenement"][:7]
    stats = client.get(f"/api/incidents/stats?month={month}")
    assert stats.status_code == 200, stats.text
    assert stats.json()["by_type"]["PANNE_VEHICULE"]["count"] == 1

    resolved = client.post(f"/api/incidents/{payload['id']}/resolve", json={"note": "replacement assigned"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolu"] is True


def test_client_complaint_feeds_r4_12_kpi_snapshot(db):
    target = date(2026, 5, 20)
    db.add(
        KpiDefinition(
            code="R4-12",
            nom="Customer Incidents / MKm",
            description="Client logistics incidents per MKm sold",
            unite="Nb",
            frequence=KpiFrequence.monthly,
            direction=KpiDirection.DOWN,
            target_2025=13,
            green_max=14,
            yellow_max=15,
        )
    )
    db.flush()
    _seed_mission(db, target=target, km=100000)
    incident = IncidentService(db).log(
        type=EvenementType.CLIENT_COMPLAINT,
        description="Late delivery complaint",
    )
    incident.date_evenement = datetime(2026, 5, 20, 12, 0)
    db.commit()

    assert run_monthly(2026, 5, db=db) == 1
    monthly = db.query(KpiMensuel).one()
    assert float(monthly.valeur) == 10.0
    assert monthly.status == KpiStatus.OK
    assert db.query(EvenementAlea).count() == 1
