"""Tests for explainable routing (W2.5)."""

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


def test_explain_returns_rationale(client, base_plan):
    tid = next(t["truck_id"] for t in base_plan["trucks"] if t["trips"])
    r = client.post("/api/planning/daily/explain", json={"plan": base_plan, "truck_id": tid})
    assert r.status_code == 200
    j = r.json()
    assert j["truck_id"] == tid
    assert isinstance(j["summary"], str) and len(j["summary"]) > 20
    assert j["facts"]["binding_constraint"] in ("weight", "positions")
    assert isinstance(j["stop_reasons"], list)


def test_explain_utilization_is_per_trip(client, base_plan):
    """Per-trip capacity binds in the solver, so peak utilisation must never
    exceed 100% — guards against the daily-sum bug."""
    for t in base_plan["trucks"]:
        if not t["trips"]:
            continue
        j = client.post(
            "/api/planning/daily/explain",
            json={"plan": base_plan, "truck_id": t["truck_id"]},
        ).json()
        assert j["facts"]["peak_utilization_positions_pct"] <= 100.5
        assert j["facts"]["peak_utilization_kg_pct"] <= 100.5


def test_explain_unknown_truck_404(client, base_plan):
    r = client.post("/api/planning/daily/explain", json={"plan": base_plan, "truck_id": 123456})
    assert r.status_code == 404
