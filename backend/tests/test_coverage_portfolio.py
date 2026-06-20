"""Regression tests for the coverage-first CO₂ portfolio (W2.1).

These lock in the fix for the objective-mode flaw (a single fixed-makespan solve
could abandon a serviceable customer and mislabel CO₂). They test the SELECTION
MECHANISM deterministically — by stubbing the per-setting solve — rather than the
time-limited OR-Tools output, which is non-deterministic under load. The real-data
behaviour (every objective serves all serviceable customers; green CO₂ ≤ fast) is
covered by the always-valid invariants in test_optimizer_golden.py and was
verified manually.
"""

from pathlib import Path

import pytest

from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig

ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"


def _builder(objective="balanced", **cfg):
    return DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(objective=objective, **cfg))


def _plan(unassigned_reasons=(), co2=0.0, cost=0.0, finish=("12:00",), sustainability=True):
    plan = {
        "unassigned": [{"unassigned_reason": r} for r in unassigned_reasons],
        "estimated_co2_kg": co2,
        "estimated_cost_tnd": {"total": cost},
        "trucks": [{"trips": [{"return_at": rt} for rt in finish]}],
    }
    if sustainability:
        plan["sustainability"] = {"objective": "x", "co2_kg": co2}
    return plan


# ───────────────────────────────────────────── recoverable-drop classifier
def test_recoverable_drops_ignores_hard_drops():
    b = _builder()
    plan = _plan(unassigned_reasons=[
        "Export / foreign site — not a domestic truck run",     # hard
        "Could not locate “Xyz”",                                # hard
        "30 positions exceeds the largest truck (24) — needs a delivery split",  # hard
        "12.0 m³ exceeds the largest truck (90 m³) — the load cubes out",        # hard
        "No feasible vehicle/time slot in the working day",      # RECOVERABLE
        "Outside customer time window",                          # RECOVERABLE
    ])
    assert b._recoverable_drops(plan) == 2


def test_recoverable_drops_zero_when_all_hard():
    b = _builder()
    assert b._recoverable_drops(_plan(unassigned_reasons=["Export / foreign site"])) == 0
    assert b._recoverable_drops(_plan(unassigned_reasons=[])) == 0


# ─────────────────────────────────────────────────── finish-time helper
def test_plan_finish_minutes_takes_latest_return():
    assert DailyPlanBuilder._plan_finish_minutes(_plan(finish=("11:30", "25:14", "18:00"))) == 25 * 60 + 14
    assert DailyPlanBuilder._plan_finish_minutes({"trucks": []}) == 0


# ─────────────────────────────────────────── objective-specific secondary
def test_secondary_metric_per_objective():
    p = _plan(co2=500.0, cost=1234.0, finish=("19:30",))
    assert _builder("green")._secondary_metric(p) == 500.0
    assert _builder("cost")._secondary_metric(p) == 500.0
    assert _builder("fast")._secondary_metric(p) == 19 * 60 + 30
    assert _builder("balanced")._secondary_metric(p) == 1234.0


# ───────────────────────────────────── portfolio selection (coverage-first)
def test_portfolio_picks_fewest_unassigned_then_lowest_secondary(monkeypatch):
    b = _builder("green")
    # One canned plan per makespan override; the override-0 plan serves all but is
    # high CO₂, override-6 also serves all and is lowest CO₂, override-12 drops one.
    canned = {
        0: _plan(unassigned_reasons=[], co2=900.0),
        6: _plan(unassigned_reasons=[], co2=700.0),
        12: _plan(unassigned_reasons=["No feasible vehicle/time slot"], co2=600.0),
    }
    monkeypatch.setattr(b, "_build_once", lambda day, sf=None: canned[b._makespan_override])
    best = b._build_portfolio(day=None)
    # override-6 wins: full coverage (beats override-12) and lowest CO₂ (beats 0).
    assert best["estimated_co2_kg"] == 700.0
    assert best["objective"] == "green"
    assert best["sustainability"]["objective"] == "green"


def test_portfolio_includes_seed_candidate(monkeypatch):
    b = _builder("balanced")
    seed = _plan(unassigned_reasons=[], cost=500.0)        # already full coverage, cheapest
    canned = {c: _plan(unassigned_reasons=[], cost=900.0) for c in b._PORTFOLIO_COEFS}
    monkeypatch.setattr(b, "_build_once", lambda day, sf=None: canned[b._makespan_override])
    best = b._build_portfolio(day=None, seed=seed)
    assert best["estimated_cost_tnd"]["total"] == 500.0   # the seed won


# ───────────────────────────────────────────── build() dispatch behaviour
def test_green_always_runs_portfolio(monkeypatch):
    b = _builder("green")
    calls = {"n": 0}

    def fake_once(day, sf=None):
        calls["n"] += 1
        return _plan(unassigned_reasons=[], co2=100.0)
    monkeypatch.setattr(b, "_build_once", fake_once)
    b.build(day=None)
    assert calls["n"] == len(b._PORTFOLIO_COEFS)   # 3 portfolio solves, no single-solve shortcut


def test_balanced_single_solve_when_no_recoverable_drop(monkeypatch):
    b = _builder("balanced")
    calls = {"n": 0}

    def fake_once(day, sf=None):
        calls["n"] += 1
        return _plan(unassigned_reasons=["Export / foreign site"], cost=100.0)  # only a hard drop
    monkeypatch.setattr(b, "_build_once", fake_once)
    b.build(day=None)
    assert calls["n"] == 1   # no escalation


def test_balanced_escalates_on_recoverable_drop(monkeypatch):
    b = _builder("balanced")
    calls = {"n": 0}

    def fake_once(day, sf=None):
        calls["n"] += 1
        return _plan(unassigned_reasons=["No feasible vehicle/time slot"], cost=100.0)
    monkeypatch.setattr(b, "_build_once", fake_once)
    b.build(day=None)
    assert calls["n"] == 1 + len(b._PORTFOLIO_COEFS)   # seed + portfolio


def test_coverage_portfolio_can_be_disabled(monkeypatch):
    b = _builder("balanced", coverage_portfolio=False)
    calls = {"n": 0}

    def fake_once(day, sf=None):
        calls["n"] += 1
        return _plan(unassigned_reasons=["No feasible vehicle/time slot"], cost=100.0)
    monkeypatch.setattr(b, "_build_once", fake_once)
    b.build(day=None)
    assert calls["n"] == 1   # single solve, no portfolio even with a recoverable drop
