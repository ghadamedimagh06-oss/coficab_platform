"""Tests for the Carbon & ESG feature (W2.1).

Covers the emissions math, the per-plan sustainability block, the objective
modes, and the /pareto + /esg-report endpoints.
"""

import os
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig, CostConfig

ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"
DAY = date(2026, 5, 26)


def _build(objective="balanced", seconds=3):
    cfg = DailyPlanConfig(prefer_ortools=True, objective=objective, global_solver_seconds=seconds)
    return DailyPlanBuilder(WEEKLY_DIR, cfg=cfg).build(DAY)


def test_plan_includes_sustainability_block():
    plan = _build()
    assert "sustainability" in plan
    assert "estimated_co2_kg" in plan
    s = plan["sustainability"]
    for key in (
        "co2_kg", "baseline_co2_kg", "co2_saved_kg", "co2_saved_pct",
        "fuel_liters", "planned_distance_km", "baseline_distance_km",
        "trees_year_equivalent", "car_km_equivalent",
    ):
        assert key in s, f"missing sustainability key: {key}"


def test_emissions_invariants():
    plan = _build()
    s = plan["sustainability"]
    # Non-negative physical quantities.
    assert s["co2_kg"] >= 0
    assert s["fuel_liters"] >= 0
    assert s["planned_distance_km"] >= 0
    # The unconsolidated baseline can never be shorter than the optimised plan.
    assert s["baseline_distance_km"] >= s["planned_distance_km"] - 0.1
    assert s["baseline_co2_kg"] >= s["co2_kg"] - 0.1
    # Saved % is a real percentage.
    assert 0 <= s["co2_saved_pct"] <= 100
    # estimated_co2_kg mirrors the block.
    assert plan["estimated_co2_kg"] == s["co2_kg"]


def test_co2_math_matches_factors():
    """CO₂ = km × (L/100km) ÷ 100 × kg/L, exactly."""
    b = DailyPlanBuilder(WEEKLY_DIR, cost_config=CostConfig())
    cc = b.cost_config
    km = 100.0
    expected = km * cc.fuel_consumption_l_per_100km / 100.0 * cc.co2_kg_per_liter_diesel
    assert b._co2_kg(km) == pytest.approx(expected)


def test_objective_modes_all_build():
    for obj in ("green", "balanced", "fast", "cost"):
        plan = _build(objective=obj)
        assert plan["objective"] == obj
        assert plan["sustainability"]["objective"] == obj
        # Every mode must still produce a usable plan.
        assert any(t["trips"] for t in plan["trucks"])


def test_makespan_coef_presets():
    assert DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective="green"))._makespan_coef() == 0
    assert DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective="cost"))._makespan_coef() == 0
    assert DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective="fast"))._makespan_coef() == 12
    # balanced falls back to the configured makespan_cost_coef
    cfg = DailyPlanConfig(objective="balanced", makespan_cost_coef=3)
    assert DailyPlanBuilder(WEEKLY_DIR, cfg=cfg)._makespan_coef() == 3


# --------------------------------------------------------------- endpoint tests

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_esg_report_endpoint(client):
    r = client.get("/api/planning/daily/esg-report", params={"day": DAY.isoformat(), "objective": "green"})
    assert r.status_code == 200
    j = r.json()
    assert j["objective"] == "green"
    assert "headline" in j and "co2_saved_kg" in j["headline"]
    assert "methodology" in j
    assert isinstance(j["per_truck"], list)


def test_pareto_endpoint(client):
    r = client.post(
        "/api/planning/daily/pareto",
        json={"day": DAY.isoformat(), "objectives": ["green", "fast"]},
    )
    assert r.status_code == 200
    j = r.json()
    objs = {p["objective"] for p in j["points"]}
    assert objs == {"green", "fast"}
    assert set(j["plans"].keys()) == {"green", "fast"}
    # Recommendations point at real, evaluated objectives.
    for role in ("greenest", "fastest", "cheapest"):
        assert j["recommendations"][role] in objs
