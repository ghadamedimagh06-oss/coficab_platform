from app.models.camion import Camion, CamionStatus, CamionType


def _truck(db, plate="DRV-TEST"):
    truck = Camion(
        plate_number=plate,
        type=CamionType.PORTEUR,
        capacite_kg=9000,
        max_palettes=14,
        status=CamionStatus.DISPONIBLE,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)
    return truck


def test_admin_can_create_and_update_persistent_driver(client, db):
    truck = _truck(db)
    response = client.post(
        "/api/fleet/drivers",
        json={
            "full_name": "  Test Driver  ",
            "phone": "+216 00 000 000",
            "permis_type": "C",
            "permis_numero": " permit-001 ",
            "status": "ACTIF",
            "camion_defaut_id": truck.id,
            "shift_start": "08:00",
            "shift_end": "17:00",
        },
    )

    assert response.status_code == 201, response.text
    driver = response.json()
    assert driver["full_name"] == "Test Driver"
    assert driver["camion_defaut_id"] == truck.id

    updated = client.patch(
        f"/api/fleet/drivers/{driver['id']}",
        json={"status": "CONGE", "camion_defaut_id": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "CONGE"
    assert updated.json()["camion_defaut_id"] is None

    roster = client.get("/api/fleet/drivers")
    assert roster.status_code == 200
    assert roster.json()[0]["permis_numero"] == "PERMIT-001"


def test_driver_default_truck_and_permit_conflicts_are_rejected(client, db):
    truck = _truck(db, "DRV-CONFLICT")
    first = client.post(
        "/api/fleet/drivers",
        json={
            "full_name": "First Driver",
            "permis_type": "C",
            "permis_numero": "PERMIT-CONFLICT",
            "camion_defaut_id": truck.id,
        },
    )
    assert first.status_code == 201, first.text

    permit_conflict = client.post(
        "/api/fleet/drivers",
        json={
            "full_name": "Second Driver",
            "permis_type": "C",
            "permis_numero": "PERMIT-CONFLICT",
        },
    )
    assert permit_conflict.status_code == 409

    truck_conflict = client.post(
        "/api/fleet/drivers",
        json={
            "full_name": "Third Driver",
            "permis_type": "C",
            "permis_numero": "PERMIT-OTHER",
            "camion_defaut_id": truck.id,
        },
    )
    assert truck_conflict.status_code == 409
