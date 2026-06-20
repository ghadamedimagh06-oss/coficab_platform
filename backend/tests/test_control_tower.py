"""Tests for the live control-tower snapshot (W3.2).

Everything is computed deterministically from a static plan, so positions,
states and predicted-late alerts are fully reproducible.
"""

import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.services.control_tower import live_snapshot, _to_min


def _plan():
    """One working truck (depot → A → B → depot) and one idle truck. A has no
    window; B's window [07:30, 09:00] is comfortably met by its 08:00 arrival,
    so the base plan raises no alerts."""
    return {
        "depot": {"lat": 36.0, "lon": 10.0},
        "trucks": [
            {"truck_id": 1, "truck_label": "Truck 1", "trips": [
                {"trip_id": "1-1", "depart_at": "06:00", "return_at": "12:00", "stops": [
                    {"id": 11, "client": "A", "lat": 36.5, "lon": 10.0,
                     "etd": "07:00", "eta": "07:20", "constraints": {}},
                    {"id": 12, "client": "B", "lat": 36.5, "lon": 10.5,
                     "etd": "08:00", "eta": "08:20",
                     "constraints": {"time_window": ["07:30", "09:00"]}},
                ]},
            ]},
            {"truck_id": 2, "truck_label": "Truck 2", "trips": []},
        ],
        "unassigned": [],
    }


# ───────────────────────────────────────────────────────────── positions
def test_truck_en_route_position_is_interpolated():
    s = live_snapshot(_plan(), now_min=_to_min("06:30"))
    t1 = s["trucks"][0]
    assert t1["state"] == "en_route"
    # halfway (06:00→07:00) from depot(36.0) to A(36.5)
    assert t1["position"][0] == pytest.approx(36.25, abs=0.01)
    assert t1["position"][1] == pytest.approx(10.0, abs=0.01)
    assert t1["to"] == "A"


def test_truck_at_stop_during_service():
    s = live_snapshot(_plan(), now_min=_to_min("07:10"))
    assert s["trucks"][0]["state"] == "at_stop"


def test_pre_dispatch_and_completed_states():
    early = live_snapshot(_plan(), now_min=_to_min("05:00"))
    late = live_snapshot(_plan(), now_min=_to_min("13:00"))
    assert early["trucks"][0]["state"] == "pre_dispatch"
    assert late["trucks"][0]["state"] == "completed"


def test_idle_truck_has_no_position():
    s = live_snapshot(_plan(), now_min=_to_min("08:00"))
    idle = next(t for t in s["trucks"] if t["truck_id"] == 2)
    assert idle["state"] == "idle"
    assert idle["position"] is None
    assert idle["total_stops"] == 0


# ───────────────────────────────────────────────────── progress / next stop
def test_next_stop_and_minutes_to_next():
    s = live_snapshot(_plan(), now_min=_to_min("06:30"))
    t1 = s["trucks"][0]
    assert t1["next_stop"]["client"] == "A"
    assert t1["minutes_to_next_stop"] == 30   # arrival 07:00 − now 06:30
    assert t1["completed_stops"] == 0
    assert t1["remaining_stops"] == 2


def test_completed_count_advances_after_service():
    s = live_snapshot(_plan(), now_min=_to_min("07:30"))
    t1 = s["trucks"][0]
    assert t1["completed_stops"] == 1          # A done (service ended 07:20)
    assert t1["next_stop"]["client"] == "B"


def test_day_progress_pct_within_bounds():
    s = live_snapshot(_plan(), now_min=_to_min("06:30"))
    assert 0 <= s["trucks"][0]["day_progress_pct"] <= 100


# ──────────────────────────────────────────────── predicted-late alerts
def test_base_plan_has_no_alerts():
    s = live_snapshot(_plan(), now_min=_to_min("06:30"))
    assert s["alerts"] == []
    assert s["fleet"]["predicted_late_stops"] == 0


def test_injected_delay_makes_a_stop_predicted_late():
    # +90 min on Truck 1 pushes B's arrival to 09:30, past its 09:00 window.
    s = live_snapshot(_plan(), now_min=_to_min("07:00"), delays={"1": 90})
    assert len(s["alerts"]) == 1
    a = s["alerts"][0]
    assert a["client"] == "B"
    assert a["minutes_late"] == 30
    assert a["severity"] == "warning"
    assert a["upcoming"] is True
    assert s["fleet"]["predicted_late_stops"] == 1
    assert s["trucks"][0]["delay_min"] == 90


def test_delay_accepts_list_form_and_high_severity():
    # A 150-min delay → B arrives 10:30, 90 min past its 09:00 window → high.
    s = live_snapshot(_plan(), now_min=_to_min("07:00"),
                      delays=[{"truck_id": 1, "delay_min": 150}])
    a = s["alerts"][0]
    assert a["minutes_late"] == 90   # 10:30 projected vs 09:00 window
    assert a["severity"] == "high"


# ─────────────────────────────────────────────────────── fleet roll-up
def test_fleet_rollup_counts():
    s = live_snapshot(_plan(), now_min=_to_min("06:30"))
    f = s["fleet"]
    assert f["total_trucks"] == 2
    assert f["active"] == 1
    assert f["stops_total"] == 2
    assert s["as_of"] == "06:30"


def test_default_now_is_midpoint_of_day():
    # 06:00 depart ↔ 12:00 return → mid-point 09:00.
    assert live_snapshot(_plan())["as_of"] == "09:00"


def test_empty_plan_is_safe():
    s = live_snapshot({"trucks": [], "depot": {"lat": 36, "lon": 10}})
    assert s["trucks"] == []
    assert s["alerts"] == []
    assert s["fleet"]["total_trucks"] == 0


# ─────────────────────────────────────────────────────────── endpoint
def test_control_tower_endpoint_with_inline_plan():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/planning/daily/control-tower",
        json={"day": "2026-05-26", "plan": _plan(), "as_of": "06:30",
              "delays": [{"truck_id": 1, "delay_min": 90}]},
    )
    assert r.status_code == 200
    ct = r.json()["control_tower"]
    assert ct["as_of"] == "06:30"
    assert ct["fleet"]["total_trucks"] == 2
    assert any(a["client"] == "B" for a in ct["alerts"])
