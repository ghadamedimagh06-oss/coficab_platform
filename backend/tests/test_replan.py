"""Tests for self-healing re-planning (W2.4)."""

import os
from datetime import date

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

DAY = date(2026, 5, 26)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def base_plan(client):
    return client.post("/api/planning/daily/generate", json={"day": DAY.isoformat()}).json()


def _busiest_truck(plan):
    return max(
        (t for t in plan["trucks"] if t["trips"]),
        key=lambda t: sum(len(tr.get("stops", [])) for tr in t["trips"]),
    )


def test_replan_removes_disrupted_truck(client, base_plan):
    broken = _busiest_truck(base_plan)
    r = client.post(
        "/api/planning/daily/replan",
        json={"day": DAY.isoformat(), "plan": base_plan, "disrupted_truck_ids": [broken["truck_id"]]},
    )
    assert r.status_code == 200
    body = r.json()
    new_plan = body["plan"]
    assert new_plan.get("replanned") is True
    # The broken truck must carry nothing in the recovered plan.
    for t in new_plan["trucks"]:
        if t["truck_id"] == broken["truck_id"]:
            assert not t["trips"], "disrupted truck still has trips after replan"


def test_replan_diff_structure(client, base_plan):
    broken = _busiest_truck(base_plan)
    r = client.post(
        "/api/planning/daily/replan",
        json={"day": DAY.isoformat(), "plan": base_plan, "disrupted_truck_ids": [broken["truck_id"]]},
    )
    diff = r.json()["diff"]
    for key in (
        "replanned_stops", "reassignments", "reassigned_count",
        "newly_unassigned", "newly_unassigned_count", "recovered",
        "cost_delta_tnd", "co2_delta_kg",
    ):
        assert key in diff, f"diff missing {key}"
    assert diff["replanned_stops"] > 0
    # Counts agree with their lists.
    assert diff["reassigned_count"] == len(diff["reassignments"])
    assert diff["newly_unassigned_count"] == len(diff["newly_unassigned"])


def test_replan_no_remaining_is_400(client):
    empty_plan = {"trucks": [], "unassigned": []}
    r = client.post(
        "/api/planning/daily/replan",
        json={"day": DAY.isoformat(), "plan": empty_plan},
    )
    assert r.status_code == 400


def test_replan_all_trucks_down_is_400(client, base_plan):
    all_ids = [t["truck_id"] for t in base_plan["trucks"]]
    r = client.post(
        "/api/planning/daily/replan",
        json={"day": DAY.isoformat(), "plan": base_plan, "disrupted_truck_ids": all_ids},
    )
    assert r.status_code == 400
