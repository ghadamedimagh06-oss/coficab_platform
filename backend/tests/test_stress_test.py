"""Tests for the Stress-Test Scenario Lab (W2.2)."""

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


def test_demand_multiplier_scales_demand():
    """The demand_multiplier knob must scale a delivery's positions and kg."""
    from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig
    from pathlib import Path

    weekly = Path(__file__).resolve().parents[2] / "weekly planning"
    row = {"row_number": 1, "client": "X", "position_count": 10, "total_gross_weight_kg": 1000}

    base = DailyPlanBuilder(weekly, cfg=DailyPlanConfig(demand_multiplier=1.0))._delivery_from_row(row, DAY)
    scaled = DailyPlanBuilder(weekly, cfg=DailyPlanConfig(demand_multiplier=1.5))._delivery_from_row(row, DAY)

    assert base["quantity_positions"] == 10
    assert scaled["quantity_positions"] == 15
    assert scaled["quantity_kg"] == pytest.approx(1500)


def test_stress_test_endpoint(client):
    r = client.post(
        "/api/planning/daily/stress-test",
        json={"day": DAY.isoformat(), "scenarios": [{"label": "Demand +30%", "volume_multiplier": 1.3}]},
    )
    assert r.status_code == 200
    j = r.json()
    assert "baseline" in j and "served_pct" in j["baseline"]
    assert len(j["scenarios"]) == 1
    sc = j["scenarios"][0]
    assert sc["feasible"] is True
    assert "deltas" in sc and "served_pct" in sc["deltas"]
    # +30% volume cannot serve a higher fraction than the baseline.
    assert sc["served_pct"] <= j["baseline"]["served_pct"] + 0.01


def test_stress_test_removing_all_trucks_is_infeasible(client):
    # Provide a tiny fleet then remove it entirely.
    fleet = [{"truck_id": 1, "truck_label": "Only", "capacity_positions": 14, "capacity_kg": 10000}]
    r = client.post(
        "/api/planning/daily/stress-test",
        json={
            "day": DAY.isoformat(),
            "trucks": fleet,
            "scenarios": [{"label": "Lose everything", "remove_truck_ids": [1]}],
        },
    )
    assert r.status_code == 200
    sc = r.json()["scenarios"][0]
    assert sc["feasible"] is False


def test_default_scenarios_generated(client):
    """With no scenarios supplied, the server generates a default battery."""
    fleet = [
        {"truck_id": 1, "truck_label": "A", "capacity_positions": 24, "capacity_kg": 24000},
        {"truck_id": 2, "truck_label": "B", "capacity_positions": 14, "capacity_kg": 10000},
    ]
    r = client.post(
        "/api/planning/daily/stress-test",
        json={"day": DAY.isoformat(), "trucks": fleet},
    )
    assert r.status_code == 200
    labels = [s["label"] for s in r.json()["scenarios"]]
    assert any("biggest" in lbl.lower() for lbl in labels)
    assert any("+30%" in lbl or "+20%" in lbl for lbl in labels)
