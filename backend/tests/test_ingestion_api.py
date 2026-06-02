from datetime import date, timedelta

import pandas as pd

from app.models.client import Client
from app.models.demande import DemandeLocal
from app.models.ingestion_log import IngestionLog


def test_manual_demande_endpoint_creates_demande(client, db):
    tomorrow = date.today() + timedelta(days=1)
    db.add(Client(id=1201, nom="Manual Client"))
    db.commit()

    response = client.post(
        "/api/ingestion/demande",
        json={
            "client_id": 1201,
            "quantite_kg": 750,
            "nombre_palettes": 2,
            "date_livraison": tomorrow.isoformat(),
            "priorite": "HAUTE",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["client_id"] == 1201
    assert payload["source_import"] == "manual"
    assert db.query(DemandeLocal).count() == 1


def test_ingestion_logs_detail_and_retry(client, db, tmp_path):
    tomorrow = date.today() + timedelta(days=1)
    db.add(Client(id=1301, nom="Retry Client"))
    workbook = tmp_path / "retry.xlsx"
    pd.DataFrame(
        [
            {
                "client_id": 1301,
                "quantite_kg": 950,
                "date_livraison": tomorrow.isoformat(),
                "priorite": "NORMALE",
            }
        ]
    ).to_excel(workbook, index=False)
    log = IngestionLog(
        file_name=workbook.name,
        file_path=str(workbook),
        status="failed",
        inserted_rows=0,
        total_rows=1,
        error_message="previous parse failed",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    listed = client.get("/api/ingestion/logs")
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] == 1

    detail = client.get(f"/api/ingestion/logs/{log.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["error_message"] == "previous parse failed"

    retried = client.post(f"/api/ingestion/logs/{log.id}/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "success"
    assert retried.json()["inserted_rows"] == 1
    assert db.query(DemandeLocal).count() == 1

    logs_after_retry = client.get("/api/ingestion/logs?limit=10")
    assert logs_after_retry.status_code == 200
    assert logs_after_retry.json()["count"] == 2
