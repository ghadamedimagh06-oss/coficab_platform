"""Tests for the agentic copilot write-tools (W3.1).

The intent parser and the deterministic summary are unit-tested directly (fast,
LLM-free). The /api/copilot/action endpoint is exercised over a real built plan
for the explain and breakdown-recovery (replan) actions.
"""

import os
from datetime import date

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.services import copilot_actions

DAY = date(2026, 5, 26)


# ───────────────────────────────────────────────────────── intent parser
@pytest.mark.parametrize("text,expected", [
    ("summary", "summary"),
    ("give me an overview", "summary"),
    ("how's the plan?", "summary"),
    ("explain truck 5", "explain"),
    ("why is truck 3 routed like that", "explain"),
    ("truck 3 broke down", "replan"),
    ("break down truck 2 and replan", "replan"),
    ("help", "help"),
    ("what can you do", "help"),
    ("make me a coffee", "unknown"),
    ("", "unknown"),
])
def test_interpret_actions(text, expected):
    assert copilot_actions.interpret(text)["action"] == expected


def test_interpret_extracts_truck_for_explain():
    assert copilot_actions.interpret("explain truck 5")["truck_id"] == 5


def test_interpret_extracts_multiple_trucks_for_replan():
    assert copilot_actions.interpret("break down trucks 2 and 4, then replan")["truck_ids"] == [2, 4]


def test_breakdown_beats_explain_when_both_present():
    # "why did truck 3 break down" — breakdown is the actionable intent.
    assert copilot_actions.interpret("truck 3 broke down, why")["action"] == "replan"


# ───────────────────────────────────────────────────── deterministic summary
def _synthetic_plan():
    return {
        "day": DAY.isoformat(),
        "trucks": [
            {"truck_id": 1, "truck_label": "Truck 1", "trips": [
                {"return_at": "13:30", "stops": [{"id": 1}, {"id": 2}]},
            ]},
            {"truck_id": 2, "truck_label": "Truck 2", "trips": []},  # idle
        ],
        "unassigned": [
            {"id": 9, "unassigned_reason": "Export / foreign site"},          # hard
            {"id": 10, "unassigned_reason": "No feasible vehicle/time slot"},  # serviceable
        ],
        "sustainability": {"planned_distance_km": 420.0, "co2_kg": 315.0},
        "estimated_cost_tnd": {"total": 1234.0},
    }


def test_plan_summary_counts():
    s = copilot_actions.plan_summary(_synthetic_plan())
    assert s["trucks_used"] == 1
    assert s["trips"] == 1
    assert s["stops_delivered"] == 2
    assert s["unassigned_recoverable"] == 1
    assert s["unassigned_hard"] == 1
    assert s["finish"] == "13:30"
    assert s["applies"] is False
    assert "CO₂" in s["summary"] or "km" in s["summary"]


def test_help_text():
    assert copilot_actions.help_text()["action"] == "help"


# ───────────────────────────────────────────────────────────── endpoint
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


def test_action_summary_endpoint(client, base_plan):
    r = client.post("/api/copilot/action", json={"text": "summary", "plan": base_plan})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "summary"
    assert body["trucks_used"] >= 1
    assert body["applies"] is False


def test_action_help_and_unknown(client):
    assert client.post("/api/copilot/action", json={"text": "help"}).json()["action"] == "help"
    unk = client.post("/api/copilot/action", json={"text": "tell me a joke"}).json()
    assert unk["action"] == "unknown"
    assert unk.get("can_chat") is True


def test_action_summary_without_plan(client):
    body = client.post("/api/copilot/action", json={"text": "summary"}).json()
    assert body["action"] == "summary"
    assert body["applies"] is False  # graceful "no plan loaded" message


def test_action_explain_endpoint(client, base_plan):
    truck_id = _busiest_truck(base_plan)["truck_id"]
    r = client.post(
        "/api/copilot/action",
        json={"text": f"explain truck {truck_id}", "plan": base_plan},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "explain"
    assert body["summary"]
    assert body["explain"]["truck_label"]
    assert body["applies"] is False


def test_action_replan_endpoint_returns_applyable_recovery(client, base_plan):
    broken = _busiest_truck(base_plan)["truck_id"]
    r = client.post(
        "/api/copilot/action",
        json={"text": f"truck {broken} broke down, replan", "plan": base_plan},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "replan"
    assert body["applies"] is True
    assert body["plan"]["replanned"] is True
    # The broken truck carries nothing in the proposed recovery.
    for t in body["plan"]["trucks"]:
        if t["truck_id"] == broken:
            assert not t["trips"]
    assert "diff" in body and body["diff"]["replanned_stops"] > 0
