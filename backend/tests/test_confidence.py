"""Tests for the Monte-Carlo plan-confidence simulator (W2.3)."""

import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.services.simulation_service import simulate_plan


def _plan(window_end, travel=60, service=20, depart="08:00"):
    """A one-truck, one-stop plan. Arrival ≈ depart+travel; `window_end` sets the
    deadline so we can force the stop to be reliably early or reliably late."""
    return {
        "trucks": [{
            "truck_label": "T1",
            "trips": [{
                "depart_at": depart,
                "return_at": "10:00",
                "stops": [{
                    "client": "ACME",
                    "travel_min": travel,
                    "service_min": service,
                    "etd": "09:00",
                    "eta": "09:20",
                    "constraints": {"time_window": ["08:00", window_end]},
                }],
            }],
        }],
    }


def test_generous_window_is_high_confidence():
    # Arrival ~09:00, window closes 23:00 -> essentially always on time.
    rep = simulate_plan(_plan("23:00"), runs=300)
    assert rep["expected_otif_pct"] >= 99.0
    assert rep["confidence_pct"] >= 99.0
    assert rep["all_ontime_pct"] >= 99.0


def test_tight_past_window_is_low_confidence():
    # Arrival ~09:00 but the window closed at 08:30 -> always late.
    rep = simulate_plan(_plan("08:30"), runs=300)
    assert rep["expected_otif_pct"] == 0.0
    assert rep["confidence_pct"] == 0.0
    assert rep["fragile_stops"][0]["late_pct"] == 100.0


def test_report_invariants():
    rep = simulate_plan(_plan("09:10"), runs=200)
    assert 0 <= rep["confidence_pct"] <= 100
    assert 0 <= rep["expected_otif_pct"] <= 100
    assert rep["finish_p50"] is not None
    # fragile stops are sorted by late frequency descending
    pcts = [f["late_pct"] for f in rep["fragile_stops"]]
    assert pcts == sorted(pcts, reverse=True)


def test_determinism_same_seed():
    a = simulate_plan(_plan("09:10"), runs=200, seed=7)
    b = simulate_plan(_plan("09:10"), runs=200, seed=7)
    assert a["expected_otif_pct"] == b["expected_otif_pct"]
    assert a["confidence_pct"] == b["confidence_pct"]


def test_empty_plan():
    rep = simulate_plan({"trucks": []}, runs=100)
    assert rep["runs"] == 0
    assert rep["fragile_stops"] == []


def test_confidence_endpoint_with_inline_plan():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/planning/daily/confidence",
        json={"day": "2026-05-26", "plan": _plan("23:00"), "runs": 150},
    )
    assert r.status_code == 200
    conf = r.json()["confidence"]
    assert conf["confidence_pct"] >= 99.0
    assert conf["stops_simulated"] == 1
