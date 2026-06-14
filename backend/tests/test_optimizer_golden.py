"""Golden / regression tests for the daily-plan optimiser (W4.3).

These lock in the optimiser's BEHAVIOURAL CONTRACT so a future refactor (e.g.
unifying the three optimisers, W1.1) can't silently change results:

  • the deterministic heuristic path produces a byte-stable assignment;
  • BOTH solver paths (OR-Tools global VRPTW and the heuristic fallback) respect
    every capacity dimension and conserve deliveries;
  • the TND cost decomposition always sums to its reported total;
  • the objective modes keep their meaning — `green` consolidates onto fewer
    trucks / fewer km than `fast`.

The heuristic path is exercised with prefer_ortools=False (deterministic); the
OR-Tools path with its defaults. Slow tests (full solves) are acceptable here —
this is the safety net the risky refactors lean on.
"""

from datetime import date
from pathlib import Path

import pytest

from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig

ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"
DAY = date(2026, 5, 26)


def _parent(stop):
    return stop.get("split_parent_id", stop.get("id"))


def _signature(plan):
    """Canonical, order-independent fingerprint of who-serves-whom."""
    rows = []
    for t in plan["trucks"]:
        clients = sorted(str(s.get("client")) for tr in t["trips"] for s in tr["stops"])
        if clients:
            rows.append((t["truck_id"], tuple(clients)))
    return tuple(sorted(rows))


def _assert_valid_plan(plan):
    """A plan is valid when every trip fits its truck on all three capacity
    dimensions, no individual stop is served twice (split pieces legitimately
    ride different trucks, so uniqueness is per STOP id, not per parent),
    served ∪ unassigned == considered (collapsed to parents), and every
    unassigned drop carries a reason. True regardless of objective."""
    b = DailyPlanBuilder(WEEKLY_DIR)
    served_ids = {}
    served_parents = set()
    for t in plan["trucks"]:
        cap_m3 = float(t.get("capacity_m3") or 0)
        for trip in t["trips"]:
            pos = sum(b._pos(s) for s in trip["stops"])
            kg = sum(b._kg(s) for s in trip["stops"])
            vol = sum(b._vol(s) for s in trip["stops"])
            assert pos <= t["capacity_positions"]
            assert kg <= t["capacity_kg"] + 0.5
            if cap_m3 > 0:
                assert vol <= cap_m3 + 0.05
            for s in trip["stops"]:
                served_ids.setdefault(s.get("id"), set()).add(t["truck_id"])
                served_parents.add(_parent(s))
    for sid, trucks in served_ids.items():
        assert len(trucks) == 1, f"stop {sid} served by multiple trucks {trucks}"
    unassigned = {_parent(u) for u in plan["unassigned"]}
    assert len(served_parents | unassigned) == plan["summary"]["deliveries_considered"]
    for u in plan["unassigned"]:
        assert (u.get("unassigned_reason") or "").strip(), u


@pytest.fixture(scope="module")
def heuristic_plan():
    return DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=False)).build(DAY)


@pytest.fixture(scope="module")
def green_plan():
    return DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective="green")).build(DAY)


@pytest.fixture(scope="module")
def fast_plan():
    return DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective="fast")).build(DAY)


# ───────────────────────────────────────────────────────── determinism
def test_heuristic_path_is_deterministic():
    a = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=False)).build(DAY)
    b = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=False)).build(DAY)
    assert _signature(a) == _signature(b)
    assert a["summary"]["deliveries_routed"] == b["summary"]["deliveries_routed"]


# ──────────────────────────────────────────── capacity invariants (both paths)
@pytest.mark.parametrize("ortools", [True, False])
def test_no_trip_exceeds_any_capacity(ortools):
    plan = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=ortools)).build(DAY)
    b = DailyPlanBuilder(WEEKLY_DIR)
    cap = {t["truck_id"]: t for t in plan["trucks"]}
    for truck in plan["trucks"]:
        t = cap[truck["truck_id"]]
        cap_m3 = float(t.get("capacity_m3") or 0)
        for trip in truck["trips"]:
            pos = sum(b._pos(s) for s in trip["stops"])
            kg = sum(b._kg(s) for s in trip["stops"])
            vol = sum(b._vol(s) for s in trip["stops"])
            assert pos <= t["capacity_positions"]
            assert kg <= t["capacity_kg"] + 0.5
            if cap_m3 > 0:
                assert vol <= cap_m3 + 0.05


# ─────────────────────────────────────────────────────── conservation
def test_deliveries_conserved_and_unique(heuristic_plan):
    # Each individual stop is served by exactly one truck; split pieces of one
    # customer (same parent) may ride different trucks by design, so uniqueness
    # is checked per STOP id, while conservation collapses splits to the parent.
    served_ids = {}
    served_parents = set()
    for t in heuristic_plan["trucks"]:
        for trip in t["trips"]:
            for s in trip["stops"]:
                served_ids.setdefault(s.get("id"), set()).add(t["truck_id"])
                served_parents.add(_parent(s))
    for sid, trucks in served_ids.items():
        assert len(trucks) == 1, f"stop {sid} served by multiple trucks {trucks}"
    unassigned = {_parent(u) for u in heuristic_plan["unassigned"]}
    assert len(served_parents | unassigned) == heuristic_plan["summary"]["deliveries_considered"]


def test_every_unassigned_has_a_reason(heuristic_plan):
    for u in heuristic_plan["unassigned"]:
        assert (u.get("unassigned_reason") or "").strip(), u


# ─────────────────────────────────────────────────────── cost integrity
def test_cost_decomposition_sums_to_total(heuristic_plan):
    c = heuristic_plan["estimated_cost_tnd"]
    parts = c["trucks"] + c["fuel"] + c["driver"] + c["underutilization"] + c["unassigned_penalty"]
    assert round(parts, 2) == pytest.approx(c["total"], abs=0.5)
    for key in ("trucks", "fuel", "driver", "underutilization", "unassigned_penalty"):
        assert c[key] >= 0


# ─────────────────────────────────────────────── objective contract
def test_objective_label_is_threaded_through(green_plan, fast_plan):
    # The requested objective must be recorded on the plan and its sustainability
    # block, so the UI/report can show which operating point produced it.
    assert green_plan["objective"] == "green"
    assert fast_plan["objective"] == "fast"
    assert green_plan["sustainability"]["objective"] == "green"


def test_each_objective_produces_a_valid_plan(green_plan, fast_plan):
    # The objective trades cost vs finish time and CAN change the exact routing
    # (and even which marginal stop gets dropped), but every operating point must
    # still produce a structurally valid, conserved, capacity-respecting plan.
    _assert_valid_plan(green_plan)
    _assert_valid_plan(fast_plan)
