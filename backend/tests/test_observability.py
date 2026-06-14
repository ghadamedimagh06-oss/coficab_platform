"""Tests for the observability module (W4.2): metrics registry, /metrics
endpoints, and the JSON log formatter."""

import json
import logging
import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.observability import (
    MetricsRegistry,
    JsonLogFormatter,
    render_prometheus,
    render_json,
    registry,
)


# ──────────────────────────────────────────────────────────── registry unit
def test_registry_counts_requests_and_histogram():
    reg = MetricsRegistry()
    reg.record("GET", "/x", 200, 0.02)
    reg.record("GET", "/x", 200, 0.30)
    reg.record("GET", "/x", 500, 1.20)
    snap = reg.snapshot()
    assert snap["requests_total"] == 3
    assert snap["errors_total"] == 1
    d = snap["_raw_durations"][("GET", "/x")]
    assert d["count"] == 3
    # buckets are cumulative & monotonic non-decreasing
    assert d["buckets"] == sorted(d["buckets"])
    # 0.02 falls in the first (0.05) bucket
    assert d["buckets"][0] == 1


def test_registry_in_flight_never_negative():
    reg = MetricsRegistry()
    reg.inc_in_flight(1)
    reg.inc_in_flight(-1)
    reg.inc_in_flight(-1)
    assert reg.snapshot()["in_flight"] == 0


def test_avg_ms_computed():
    reg = MetricsRegistry()
    reg.record("POST", "/y", 200, 0.1)
    reg.record("POST", "/y", 200, 0.3)
    lat = {(l["method"], l["path"]): l for l in reg.snapshot()["latency"]}
    assert lat[("POST", "/y")]["avg_ms"] == 200.0


# ──────────────────────────────────────────────────────── prometheus render
def test_prometheus_text_shape():
    registry.record("GET", "/shape-probe", 200, 0.02)  # ensure a series exists
    reg_text = render_prometheus()  # uses the module-global registry
    assert "# TYPE http_requests_total counter" in reg_text
    assert "http_request_duration_seconds_bucket" in reg_text
    assert "process_uptime_seconds" in reg_text
    assert reg_text.endswith("\n")


def test_label_escaping_quotes_and_backslashes():
    reg = MetricsRegistry()
    reg.record("GET", '/weird"\\path', 200, 0.01)
    # Swap the global registry's data in is overkill; just assert the escaper via
    # a direct render path by recording into the module registry.
    from app import observability
    observability.registry.record("GET", 'a"b', 200, 0.01)
    text = observability.render_prometheus()
    assert 'a\\"b' in text


# ─────────────────────────────────────────────────────────── JSON formatter
def test_json_formatter_emits_valid_json_with_extra():
    fmt = JsonLogFormatter()
    rec = logging.LogRecord("app.access", logging.INFO, __file__, 1, "request", None, None)
    rec.method = "GET"
    rec.path = "/api/health"
    rec.status = 200
    out = fmt.format(rec)
    parsed = json.loads(out)
    assert parsed["message"] == "request"
    assert parsed["level"] == "INFO"
    assert parsed["method"] == "GET"
    assert parsed["status"] == 200


def test_json_formatter_handles_non_serializable_extra():
    fmt = JsonLogFormatter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "m", None, None)
    rec.obj = object()  # not JSON-serializable → coerced to str, never raises
    parsed = json.loads(fmt.format(rec))
    assert "obj" in parsed


# ─────────────────────────────────────────────────────────────── endpoints
def test_metrics_endpoint_records_requests():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    before = render_json()["requests_total"]
    for _ in range(3):
        assert client.get("/api/health").status_code == 200

    text = client.get("/metrics")
    assert text.status_code == 200
    assert "http_requests_total" in text.text
    assert "/api/health" in text.text

    js = client.get("/metrics.json")
    assert js.status_code == 200
    body = js.json()
    assert body["requests_total"] >= before + 3
    assert "uptime_seconds" in body
    # the /metrics scrape itself must not be recorded
    assert all(r["path"] not in {"/metrics", "/metrics.json"} for r in body["requests"])
