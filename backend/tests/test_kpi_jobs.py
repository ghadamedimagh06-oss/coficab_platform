from datetime import date

from app.agents.kpi_jobs import run_daily, run_monthly
from app.models.client import Client
from app.models.demande import DemandeLocal, Priorite, StatutDemande
from app.models.kpi import KpiDefinition, KpiDirection, KpiFrequence, KpiJournalier, KpiMensuel, KpiStatus


def _seed_otd_fixture(db, target):
    db.add(
        KpiDefinition(
            code="R4-02",
            nom="OTD",
            description="On-time delivery",
            unite="%",
            frequence=KpiFrequence.monthly,
            direction=KpiDirection.UP,
            target_2025=96,
            green_min=94,
            yellow_min=92,
        )
    )
    db.add(Client(id=1, nom="Test Client"))
    db.flush()
    db.add_all(
        [
            DemandeLocal(
                client_id=1,
                quantite_kg=80,
                quantite_livree_kg=80,
                date_livraison=target,
                statut=StatutDemande.LIVREE,
                priorite=Priorite.NORMALE,
                livree_a_temps=True,
            ),
            DemandeLocal(
                client_id=1,
                quantite_kg=20,
                quantite_livree_kg=20,
                date_livraison=target,
                statut=StatutDemande.LIVREE,
                priorite=Priorite.NORMALE,
                livree_a_temps=False,
            ),
        ]
    )
    db.commit()


def test_kpi_jobs_upsert_daily_and_monthly_snapshots(db):
    target = date(2026, 5, 20)
    _seed_otd_fixture(db, target)

    assert run_daily(target, db=db) == 1
    assert run_daily(target, db=db) == 1

    daily_rows = db.query(KpiJournalier).all()
    assert len(daily_rows) == 1
    assert float(daily_rows[0].valeur) == 80.0
    assert daily_rows[0].color == "red"

    assert run_monthly(2026, 5, db=db) == 1
    monthly = db.query(KpiMensuel).one()
    assert float(monthly.valeur) == 80.0
    assert monthly.color == "red"
    assert monthly.status == KpiStatus.ALERT


def test_kpi_recompute_endpoint_exposes_snapshots(client, db):
    target = date(2026, 5, 20)
    _seed_otd_fixture(db, target)

    response = client.post(
        "/api/metrics/kpi/recompute",
        json={"start": target.isoformat(), "end": target.isoformat()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["daily_rows"] == 1
    assert response.json()["monthly_rows"] == 1

    daily = client.get(f"/api/metrics/kpi/snapshot/daily?date={target.isoformat()}")
    assert daily.status_code == 200, daily.text
    assert daily.json()["kpis"][0]["code"] == "R4-02"
    assert daily.json()["kpis"][0]["value"] == 80.0

    monthly = client.get("/api/metrics/kpi/snapshot/monthly?ym=2026-05")
    assert monthly.status_code == 200, monthly.text
    assert monthly.json()["kpis"][0]["status"] == "ALERT"
