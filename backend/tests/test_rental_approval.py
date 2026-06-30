from datetime import date
import pytest

from app.models.rental_approval import RentalApproval
from app.routes.optimization import _approved_rental_truck, _verify_export_rental_approvals


def test_rental_approval_is_persisted_and_required_for_export(client, db):
    response = client.post(
        "/api/planning/daily/rentals/approve",
        json={
            "plan_id": "plan-123",
            "day": "2026-06-19",
            "recommendation_id": "rental-light_5_pallet",
            "rental_profile": "LIGHT_5_PALLET",
            "estimated_cost_eur": 125,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    approval = db.get(RentalApproval, payload["approval_id"])
    assert approval is not None
    assert approval.approved_by == "dev"

    truck = _approved_rental_truck(approval)
    assert truck["ownership"] == "RENTAL"
    assert truck["rental_approval_id"] == approval.id
    _verify_export_rental_approvals(
        db,
        {"trucks": [truck], "rental_base_plan_id": "plan-123"},
        date(2026, 6, 19),
    )


def test_unapproved_rental_is_rejected_for_export(db):
    try:
        _verify_export_rental_approvals(
            db,
            {"trucks": [{"ownership": "RENTAL", "rental_profile": "SEMI_TRAILER"}]},
            date(2026, 6, 19),
        )
    except ValueError as exc:
        assert "missing approval" in str(exc)
    else:
        raise AssertionError("unapproved rental should be rejected")


def test_generate_ignores_client_claimed_owned_capacity(client):
    response = client.post(
        "/api/planning/daily/generate",
        json={
            "day": "2026-05-26",
            "trucks": [
                {
                    "truck_id": 777,
                    "truck_label": "Forged owned truck",
                    "capacity_positions": 999,
                    "capacity_kg": 999999,
                    "ownership": "OWNED",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert all(truck["truck_id"] != 777 for truck in response.json()["trucks"])


def test_rental_approval_cannot_cross_base_plans(client, db):
    approval = RentalApproval(
        plan_id="base-plan-a",
        day=date(2026, 5, 26),
        recommendation_id="rental-light",
        rental_profile="LIGHT_5_PALLET",
        estimated_cost_eur=100,
        approved_by="tester",
    )
    db.add(approval)
    db.commit()
    response = client.post(
        "/api/planning/daily/generate",
        json={
            "day": "2026-05-26",
            "rental_approval_ids": [approval.id],
            "rental_base_plan_id": "base-plan-b",
        },
    )
    assert response.status_code == 400
    assert "different base plan" in response.json()["detail"]


def test_rental_approval_cannot_be_duplicated_or_modified_at_export(db):
    approval = RentalApproval(
        plan_id="base-plan",
        day=date(2026, 6, 19),
        recommendation_id="rental-light_5_pallet",
        rental_profile="LIGHT_5_PALLET",
        estimated_cost_eur=100,
        approved_by="tester",
    )
    db.add(approval)
    db.commit()
    truck = _approved_rental_truck(approval)

    with pytest.raises(ValueError, match="used more than once"):
        _verify_export_rental_approvals(
            db,
            {"trucks": [truck, dict(truck)], "rental_base_plan_id": "base-plan"},
            date(2026, 6, 19),
        )

    modified = {**truck, "capacity_kg": truck["capacity_kg"] + 1}
    with pytest.raises(ValueError, match="field was modified"):
        _verify_export_rental_approvals(
            db,
            {"trucks": [modified], "rental_base_plan_id": "base-plan"},
            date(2026, 6, 19),
        )
