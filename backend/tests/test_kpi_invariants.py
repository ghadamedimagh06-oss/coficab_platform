from datetime import date, datetime

from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.evenement import EvenementAlea, EvenementType
from app.models.kpi import KpiDefinition, KpiDirection, KpiFrequence
from app.models.plan import ModeMission, Periode, PlanMission, PlanVersion, StatutMission
from app.services.kpi_service import KpiService, compute_color


KPI_DEFS = [
    ("R4-06", "OTIF", "%", KpiFrequence.monthly, KpiDirection.UP, 96, 94, 92, None, None),
    ("R4-02", "OTD", "%", KpiFrequence.monthly, KpiDirection.UP, 96, 94, 92, None, None),
    ("R4-02-PF", "Premium Freight Cost", "EUR", KpiFrequence.monthly, KpiDirection.DOWN, 1500, None, None, 2500, 3500),
    ("R4-03", "Premium Freight Occurrences", "Nb", KpiFrequence.monthly, KpiDirection.DOWN, 1, None, None, 3, 5),
    ("R4-13", "Fuel Consumption Efficiency", "mL/T.km", KpiFrequence.monthly, KpiDirection.DOWN, 0.14, None, None, 0.16, 0.18),
    ("R5-10", "Logistics Cost", "EUR/T", KpiFrequence.monthly, KpiDirection.DOWN, 16, None, None, 18, 20),
    ("R4-12", "Customer Incidents / MKm", "Nb", KpiFrequence.monthly, KpiDirection.DOWN, 13, None, None, 14, 15),
    ("R4", "Load Efficiency Rate", "%", KpiFrequence.daily, KpiDirection.UP, None, 80, 70, None, None),
]


def _seed_kpi_definitions(db):
    for code, label, unit, freq, direction, target, green_min, yellow_min, green_max, yellow_max in KPI_DEFS:
        db.add(
            KpiDefinition(
                code=code,
                nom=label,
                description=label,
                unite=unit,
                frequence=freq,
                direction=direction,
                target_2025=target,
                green_min=green_min,
                yellow_min=yellow_min,
                green_max=green_max,
                yellow_max=yellow_max,
            )
        )
    db.commit()


def _kpi_def(db, code):
    return db.query(KpiDefinition).filter(KpiDefinition.code == code).one()


def _seed_client(db):
    db.add(Client(id=2101, nom="KPI Client"))
    db.flush()
    return 2101


def _add_delivered(db, *, client_id, target, kg, on_time, delivered_kg=None):
    db.add(
        DemandeLocal(
            client_id=client_id,
            quantite_kg=kg,
            quantite_livree_kg=delivered_kg if delivered_kg is not None else kg,
            date_livraison=target,
            statut=StatutDemande.LIVREE,
            priorite=Priorite.NORMALE,
            livree_a_temps=on_time,
        )
    )


def _seed_mission_assets(db, target):
    camion = Camion(
        plate_number=f"KPI-{target.isoformat()}",
        type=CamionType.SEMI,
        capacite_kg=12000,
        max_palettes=24,
        status=CamionStatus.DISPONIBLE,
    )
    chauffeur = Chauffeur(
        id=12101,
        full_name="KPI Driver",
        permis_type=PermisType.CE,
        status=ChauffeurStatus.ACTIF,
    )
    plan = PlanVersion(
        plan_id=12101,
        version_number=1,
        periode=Periode.JOUR,
        date_debut=target,
        date_fin=target,
    )
    db.add_all([camion, chauffeur, plan])
    db.flush()
    return plan, camion, chauffeur


def test_kpi_invariant_otif_is_row_based_and_colored_red(db):
    target = date(2026, 5, 20)
    _seed_kpi_definitions(db)
    client_id = _seed_client(db)
    for idx in range(5):
        _add_delivered(db, client_id=client_id, target=target, kg=1000, on_time=idx >= 2)
    db.commit()

    value = KpiService(db)._compute_live("R4-06", target, target)

    assert value == 60.0
    assert compute_color(_kpi_def(db, "R4-06"), value) == "red"


def test_kpi_invariant_otd_is_quantity_weighted_and_colored_red(db):
    target = date(2026, 5, 20)
    _seed_kpi_definitions(db)
    client_id = _seed_client(db)
    _add_delivered(db, client_id=client_id, target=target, kg=8000, on_time=False)
    _add_delivered(db, client_id=client_id, target=target, kg=4500, on_time=True)
    _add_delivered(db, client_id=client_id, target=target, kg=1500, on_time=True)
    db.commit()

    value = KpiService(db)._compute_live("R4-02", target, target)

    assert value == 42.86
    assert compute_color(_kpi_def(db, "R4-02"), value) == "red"


def test_kpi_invariants_for_premium_fuel_cost_and_load(db):
    target = date(2026, 5, 20)
    _seed_kpi_definitions(db)
    plan, camion, chauffeur = _seed_mission_assets(db, target)
    db.add_all(
        [
            PlanMission(
                plan_version_id=plan.id,
                camion_id=camion.id,
                chauffeur_id=chauffeur.id,
                date_mission=target,
                statut=StatutMission.TERMINEE,
                mode=ModeMission.PREMIUM,
                cout_premium_eur=3000,
                fuel_consomme_l=15,
                charge_kg=10000,
                km_parcourus=100,
                cout_consommables_eur=50,
                cout_emballage_eur=30,
                cout_transport_eur=200,
                load_eff_pct=80,
            ),
            PlanMission(
                plan_version_id=plan.id,
                camion_id=camion.id,
                chauffeur_id=chauffeur.id,
                date_mission=target,
                statut=StatutMission.TERMINEE,
                mode=ModeMission.NORMAL,
            ),
            PlanMission(
                plan_version_id=plan.id,
                camion_id=camion.id,
                chauffeur_id=chauffeur.id,
                date_mission=target,
                statut=StatutMission.TERMINEE,
                mode=ModeMission.NORMAL,
            ),
        ]
    )
    db.commit()

    service = KpiService(db)
    start = date(2026, 5, 1)
    end = date(2026, 5, 31)

    premium_cost = service._compute_live("R4-02-PF", start, end)
    assert premium_cost == 3000.0
    assert compute_color(_kpi_def(db, "R4-02-PF"), premium_cost) == "yellow"

    premium_count = service._compute_live("R4-03", start, end)
    assert premium_count == 1.0
    assert compute_color(_kpi_def(db, "R4-03"), premium_count) == "green"

    fuel = service._compute_live("R4-13", start, end)
    assert fuel == 15.0
    assert compute_color(_kpi_def(db, "R4-13"), fuel) == "red"

    logistics = service._compute_live("R5-10", start, end)
    assert logistics == 28.0
    assert compute_color(_kpi_def(db, "R5-10"), logistics) == "red"

    load = service._compute_live("R4", target, target)
    assert load == 80.0
    assert compute_color(_kpi_def(db, "R4"), load) == "green"


def test_kpi_invariant_customer_incidents_per_mkm(db):
    target = date(2026, 5, 20)
    _seed_kpi_definitions(db)
    plan, camion, chauffeur = _seed_mission_assets(db, target)
    db.add(
        PlanMission(
            plan_version_id=plan.id,
            camion_id=camion.id,
            chauffeur_id=chauffeur.id,
            date_mission=target,
            statut=StatutMission.TERMINEE,
            km_parcourus=250000,
        )
    )
    for idx in range(5):
        db.add(
            EvenementAlea(
                type=EvenementType.CLIENT_COMPLAINT,
                description=f"Complaint {idx + 1}",
                date_evenement=datetime(2026, 5, 20, 12, idx),
            )
        )
    db.commit()

    value = KpiService(db)._compute_live("R4-12", date(2026, 5, 1), date(2026, 5, 31))

    assert value == 20.0
    assert compute_color(_kpi_def(db, "R4-12"), value) == "red"
