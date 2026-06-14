"""Tests for the volume / m³ capacity dimension (W1.4).

Cable reels cube out: a load can run out of deck VOLUME before it hits the
pallet-position or kg limit. These tests verify that:
  • a delivery's volume is its explicit m³ when given, else positions × ratio;
  • feasibility, the hard-capacity prefilter and the schedulers all respect m³;
  • a load that cubes out the biggest truck is dropped with a volume reason;
  • no dispatched trip ever exceeds its truck's m³ capacity;
  • the dimension is a safe no-op (zero behaviour change) on the default,
    position-only workbook, and for any fleet that doesn't declare capacity_m3.
"""

from datetime import date
from pathlib import Path

import pytest

from app.services.daily_plan_builder import (
    DailyPlanBuilder,
    DailyPlanConfig,
    DEFAULT_TRUCKS,
)

ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"


@pytest.fixture(scope="module")
def builder():
    return DailyPlanBuilder(WEEKLY_DIR)


# --------------------------------------------------------------- volume helper
def test_volume_derived_from_positions(builder):
    # 14 positions × 1.8 m³/position = 25.2 m³
    assert builder._vol({"quantity_positions": 14}) == pytest.approx(25.2)


def test_volume_uses_explicit_when_present(builder):
    assert builder._vol({"quantity_positions": 14, "volume_m3": 60.0}) == 60.0


def test_volume_zero_for_empty_drop(builder):
    assert builder._vol({"quantity_positions": 0}) == 0.0


def test_negative_explicit_volume_falls_back_to_derived(builder):
    # A garbage negative volume must not be trusted; derive from positions.
    assert builder._vol({"quantity_positions": 10, "volume_m3": -5}) == pytest.approx(18.0)


# ------------------------------------------------------------------- the fleet
def test_default_trucks_declare_capacity_m3():
    for t in DEFAULT_TRUCKS:
        assert float(t["capacity_m3"]) > 0


def test_clean_truck_exposes_capacity_m3(builder):
    clean = builder._clean_truck({**DEFAULT_TRUCKS[0], "trips": []})
    assert clean["capacity_m3"] == DEFAULT_TRUCKS[0]["capacity_m3"]


# --------------------------------------------------------------- feasibility
def test_feasible_trucks_excludes_too_small_by_volume(builder):
    # 60 m³ cubes out every 40 m³ truck; only the 90 m³ (id 5) and 85 m³
    # rented (id 999) trucks remain feasible.
    drop = {"quantity_positions": 1, "quantity_kg": 100, "volume_m3": 60.0}
    feasible_ids = {t["truck_id"] for t in builder._feasible_trucks(drop, DEFAULT_TRUCKS)}
    assert feasible_ids == {5, 999}


def test_fits_volume_is_noop_for_truck_without_capacity(builder):
    # A truck that doesn't declare capacity_m3 never constrains volume.
    truck = {"truck_id": 7, "capacity_positions": 14, "capacity_kg": 9000}
    assert builder._fits_volume(truck, 999.0) is True


def test_volume_enforced_requires_every_truck_to_declare_capacity(builder):
    assert builder._volume_enforced(DEFAULT_TRUCKS) is True
    mixed = DEFAULT_TRUCKS[:1] + [{"truck_id": 7, "capacity_positions": 14, "capacity_kg": 9000}]
    assert builder._volume_enforced(mixed) is False


# ------------------------------------------------ oversized volume -> dropped
def _stub_geo(builder, km=30.0):
    """Make geo resolution deterministic & offline for _evaluate."""
    builder.geo.depot = lambda: (36.78, 10.18)
    builder.geo.locate = lambda name: {
        "lat": 36.80, "lon": 10.20, "label": str(name), "km": km, "is_export": False,
    }
    # Force the haversine/table fallback so no OSRM network call is made.
    builder.cfg.use_osrm_road_matrix = False


def test_load_that_cubes_out_largest_truck_is_unassigned():
    builder = DailyPlanBuilder(WEEKLY_DIR)
    _stub_geo(builder)
    # 200 m³ exceeds the biggest truck (90 m³) → must be dropped with a volume
    # reason, even though its 1 position / 100 kg fit easily.
    drop = {
        "id": 1, "client": "Bulk Reels SA", "quantity_positions": 1,
        "quantity_kg": 100, "volume_m3": 200.0, "priority": "normal",
        "constraints": {},
    }
    trucks, unassigned, routable, _ = builder._evaluate([drop], builder.geo.depot())
    reasons = " ".join(u.get("unassigned_reason", "") for u in unassigned)
    assert any("Bulk Reels" in (u.get("client") or "") for u in unassigned)
    assert "m³" in reasons and "cubes out" in reasons
    # It must NOT have been routed onto any truck.
    routed = [s for t in trucks for trip in t["trips"] for s in trip["stops"]]
    assert all((s.get("client") or "") != "Bulk Reels SA" for s in routed)


def test_volume_fitting_load_is_served():
    builder = DailyPlanBuilder(WEEKLY_DIR)
    _stub_geo(builder)
    drop = {
        "id": 2, "client": "Normal Co", "quantity_positions": 4,
        "quantity_kg": 1000, "volume_m3": 30.0, "priority": "normal",
        "constraints": {},
    }
    trucks, unassigned, routable, _ = builder._evaluate([drop], builder.geo.depot())
    routed = [s for t in trucks for trip in t["trips"] for s in trip["stops"]]
    assert any((s.get("client") or "") == "Normal Co" for s in routed)
    assert not unassigned


# ------------------------------------------- no trip exceeds m³ on real data
def test_no_trip_exceeds_truck_volume_capacity():
    for day in (date(2026, 5, 25), date(2026, 5, 26), date(2026, 5, 28)):
        plan = DailyPlanBuilder(WEEKLY_DIR).build(day)
        cap_by_id = {t["truck_id"]: float(t.get("capacity_m3") or 0) for t in plan["trucks"]}
        b = DailyPlanBuilder(WEEKLY_DIR)
        for truck in plan["trucks"]:
            cap = cap_by_id.get(truck["truck_id"], 0)
            if cap <= 0:
                continue
            for trip in truck["trips"]:
                load_m3 = sum(b._vol(s) for s in trip["stops"])
                assert load_m3 <= cap + 0.05, (
                    f"{day} truck {truck['truck_id']} trip {trip['trip_id']} "
                    f"cubes out: {load_m3:.1f} m³ > {cap} m³"
                )


def test_plan_summary_reports_total_volume():
    plan = DailyPlanBuilder(WEEKLY_DIR).build(date(2026, 5, 26))
    assert "total_volume_m3" in plan["summary"]
    assert plan["summary"]["total_volume_m3"] >= 0


# ------------------------------------------------ backwards-compatibility
def test_volume_dimension_is_inert_on_default_data():
    """With derived volumes (no explicit m³) the deck headroom is generous, so
    enabling the volume dimension must not change how many deliveries get served
    versus running with it disabled."""
    day = date(2026, 5, 26)
    with_vol = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(enforce_volume=True)).build(day)
    without = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(enforce_volume=False)).build(day)
    assert with_vol["summary"]["deliveries_routed"] == without["summary"]["deliveries_routed"]
    assert len(with_vol["unassigned"]) == len(without["unassigned"])
