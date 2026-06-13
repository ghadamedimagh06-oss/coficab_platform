"""Execution / ePOD loop tests — docs/TMS_ROADMAP.md §4/§5.

Covers the new data path the roadmap flags as missing: confirming deliveries
advances DemandeLocal to LIVREE with the fields OTIF/OTD read, and the
mission/plan/truck state machine closes out correctly.
"""
from datetime import date, datetime

import pytest

from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.plan import (
    MissionDemande, Periode, PlanMission, PlanVersion,
    StatutMission, StatutPlan,
)
from app.models.proof import LivraisonPreuve, PodStatus
from app.services.execution_service import ExecutionError, ExecutionService
from app.services.kpi_service import _compute_otd, _compute_otif

TARGET = date(2026, 5, 21)


def _seed_plan(db, *, n_stops=2):
    client = Client(id=901, nom="Exec Client", city="Tunis")
    camion = Camion(
        plate_number="EXE-001", type=CamionType.SEMI,
        capacite_kg=12000, max_palettes=24, status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=9901, full_name="Exec Driver", phone="+21650000000",
        permis_type=PermisType.CE, status=ChauffeurStatus.ACTIF,
    )
    plan = PlanVersion(
        plan_id=9901, version_number=1, periode=Periode.JOUR,
        date_debut=TARGET, date_fin=TARGET, statut_plan=StatutPlan.DRAFT,
    )
    db.add_all([client, camion, chauffeur, plan])
    db.flush()
    mission = PlanMission(
        plan_version_id=plan.id, camion_id=camion.id, chauffeur_id=chauffeur.id,
        date_mission=TARGET, statut=StatutMission.PLANIFIEE,
    )
    db.add(mission)
    db.flush()
    stops = []
    for i in range(n_stops):
        demande = DemandeLocal(
            client_id=client.id, quantite_kg=1000, nombre_palettes=2,
            date_livraison=TARGET, statut=StatutDemande.PLANIFIEE,
            priorite=Priorite.NORMALE,
            heure_arrivee_prevue=datetime(2026, 5, 21, 10, 0),
        )
        db.add(demande)
        db.flush()
        md = MissionDemande(
            mission_id=mission.id, demande_id=demande.id, ordre_livraison=i + 1,
            eta_prevue=datetime(2026, 5, 21, 10, 0), statut="PLANIFIEE",
        )
        db.add(md)
        stops.append((demande, md))
    db.commit()
    db.refresh(plan)
    db.refresh(mission)
    return plan, mission, camion, stops


def test_full_loop_makes_otif_real(db):
    plan, mission, camion, stops = _seed_plan(db, n_stops=2)
    svc = ExecutionService(db)

    svc.validate_plan(plan.id, "admin")
    db.refresh(plan)
    assert plan.statut_plan == StatutPlan.VALIDE

    svc.start_plan(plan.id)
    db.refresh(mission)
    db.refresh(camion)
    assert mission.statut == StatutMission.EN_COURS
    assert mission.heure_sortie_reelle is not None
    assert camion.status == CamionStatus.EN_MISSION
    assert all(s[0].statut == StatutDemande.EN_COURS for s in stops)

    # Confirm both on-time and in-full.
    for _demande, md in stops:
        proof = svc.confirm_delivery(md.id, on_time=True)
        assert proof.statut == PodStatus.LIVREE

    db.refresh(mission)
    db.refresh(camion)
    db.refresh(plan)
    assert mission.statut == StatutMission.TERMINEE
    assert mission.heure_retour_reelle is not None
    assert camion.status == CamionStatus.DISPONIBLE  # released back to fleet
    assert plan.statut_plan == StatutPlan.CLOTURE

    for demande, _md in stops:
        db.refresh(demande)
        assert demande.statut == StatutDemande.LIVREE
        assert demande.livree_a_temps is True
        assert float(demande.quantite_livree_kg) == 1000.0

    assert _compute_otif(db, TARGET, TARGET) == 100.0
    assert _compute_otd(db, TARGET, TARGET) == 100.0
    assert db.query(LivraisonPreuve).count() == 2


def test_late_and_partial_delivery_lowers_otif(db):
    plan, mission, camion, stops = _seed_plan(db, n_stops=2)
    svc = ExecutionService(db)
    svc.start_plan(plan.id)

    # Stop 1: on-time but short quantity -> not in-full -> misses OTIF, makes OTD.
    svc.confirm_delivery(stops[0][1].id, quantite_livree_kg=500, on_time=True)
    # Stop 2: full but late -> misses both OTIF and OTD.
    svc.confirm_delivery(stops[1][1].id, on_time=False)

    # 2 delivered, 0 on-time-and-in-full -> OTIF 0; 1 of 2 kg on-time-ish for OTD.
    assert _compute_otif(db, TARGET, TARGET) == 0.0
    otd = _compute_otd(db, TARGET, TARGET)
    assert otd is not None and 0.0 <= otd <= 100.0

    proofs = {p.statut for p in db.query(LivraisonPreuve).all()}
    assert PodStatus.PARTIELLE in proofs


def test_exception_cancels_stop_and_closes_mission(db):
    plan, mission, camion, stops = _seed_plan(db, n_stops=2)
    svc = ExecutionService(db)
    svc.start_plan(plan.id)

    svc.confirm_delivery(stops[0][1].id, on_time=True)
    ev = svc.report_exception(stops[1][1].id, type="CLIENT_INDISPONIBLE", description="gate closed")
    assert ev.demande_id == stops[1][0].id

    db.refresh(stops[1][0])
    db.refresh(mission)
    assert stops[1][0].statut == StatutDemande.ANNULEE
    assert mission.statut == StatutMission.TERMINEE  # all stops terminal

    status = svc.plan_status(plan.id)
    assert status["stops_delivered"] == 1
    assert status["stops_cancelled"] == 1


def test_invalid_transitions_raise(db):
    plan, mission, camion, stops = _seed_plan(db, n_stops=1)
    svc = ExecutionService(db)

    with pytest.raises(ExecutionError):
        svc.get_plan(999999)

    svc.start_plan(plan.id)
    with pytest.raises(ExecutionError):
        svc.start_mission(mission.id)  # already EN_COURS

    svc.confirm_delivery(stops[0][1].id, on_time=True)
    with pytest.raises(ExecutionError):
        svc.confirm_delivery(stops[0][1].id, on_time=True)  # already delivered


def test_http_confirm_flow(client, db):
    plan, mission, camion, stops = _seed_plan(db, n_stops=1)

    r = client.post(f"/api/execution/plans/{plan.id}/validate")
    assert r.status_code == 200, r.text
    assert r.json()["statut_plan"] == "StatutPlan.VALIDE"

    r = client.post(f"/api/execution/plans/{plan.id}/start")
    assert r.status_code == 200, r.text
    assert r.json()["statut_plan"] == "StatutPlan.EXECUTE"

    md_id = stops[0][1].id
    r = client.post(f"/api/execution/stops/{md_id}/confirm", json={"on_time": True})
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "PodStatus.LIVREE"

    r = client.get(f"/api/execution/plans/{plan.id}/status")
    assert r.status_code == 200, r.text
    assert r.json()["stops_delivered"] == 1

    # Confirming a missing stop -> 404.
    assert client.post("/api/execution/stops/999999/confirm", json={}).status_code == 404
