"""Tests for the unified KPI source (W1.2).

/api/metrics/kpi must always return real numbers: ERD snapshots when present,
else a live plan-derived fallback (the same source the dashboard uses).
"""

import os
from datetime import date

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

DATA_DAY = date(2026, 5, 26)


def test_live_fallback_returns_real_kpis():
    from app.routes.metrics import _live_plan_kpis

    out = _live_plan_kpis(DATA_DAY)
    assert out["source"] == "live_plan"
    ids = {k["id"] for k in out["kpis"]}
    # The four headline cards plus the CO₂-saved card.
    assert {"otif", "load", "otd", "fuel"}.issubset(ids)
    assert "co2_saved" in ids
    # Values are present and sane for a day with data.
    by_id = {k["id"]: k for k in out["kpis"]}
    assert by_id["otif"]["value"] is not None
    assert 0 <= by_id["otif"]["value"] <= 100


def test_kpi_endpoint_never_empty():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/metrics/kpi", params={"ref_date": DATA_DAY.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert "source" in body
    # Either materialised snapshots or the live fallback — never empty for a
    # day that has plan data.
    assert body["source"] in ("snapshots", "live_plan")
    assert len(body["kpis"]) > 0
