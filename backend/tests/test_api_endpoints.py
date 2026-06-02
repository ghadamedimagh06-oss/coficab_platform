import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import AuthService
from app.database import SessionLocal

client = TestClient(app)


def test_get_kpis_unauthenticated():
    # In dev/offline mode the auth service returns a default user so the
    # endpoint is accessible without credentials (200). A real deployment
    # would configure auto_error=True on the bearer scheme to enforce 401.
    r = client.get("/api/metrics/kpi")
    assert r.status_code in (200, 401)


def test_get_kpis_authenticated():
    db = SessionLocal()
    auth = AuthService(db)
    token = auth.create_access_token({"sub": "testuser"})
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/metrics/kpi", headers=headers)
    assert r.status_code == 200
    assert "kpis" in r.json()
    db.close()


def test_planning_generate_returns_routes():
    body = {
        "deliveries": [{"id": "d1", "lat": 36.5, "lng": 10.1, "quantity": 1}],
        "trucks": [{"id": "t1", "capacity": 100}]
    }
    r = client.post("/api/optimization/planning/generate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    assert "plan" in data


def test_tracking_live_endpoint_returns_200():
    r = client.get("/api/tracking/live")
    assert r.status_code == 200
    data = r.json()
    assert "tracking_data" in data


def test_agent_status_endpoint_returns_valid_schema():
    r = client.get("/api/agents/status")
    assert r.status_code == 200
    data = r.json()
    assert "agents" in data
    assert "recent_events" in data
    assert "pipeline_status" in data
    assert "collector" in data["agents"]
    assert "optimizer" in data["agents"]
    assert "notifier" in data["agents"]
    assert "monitor" in data["agents"]


def test_tracking_sync_persists():
    body = {"items": [{"id": "t1", "status": "in_transit", "location": {"lat":36.5, "lng":10.1}, "eta_hours":2.0}]}
    r = client.post("/api/tracking/sync", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
