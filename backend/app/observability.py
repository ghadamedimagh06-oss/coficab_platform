"""Lightweight, dependency-free observability: structured logging + metrics.

Two pieces, both zero-dependency (no Prometheus client, no OpenTelemetry):

  1. `configure_logging()` — opt-in JSON log formatter so logs are machine
     parseable in production (one JSON object per line). Off by default (LOG_JSON
     unset) so local/dev output stays human-readable.

  2. An in-process metrics registry + `install_observability(app)` middleware
     that times every HTTP request and records request counts, error counts, a
     latency histogram and an in-flight gauge — keyed by the ROUTE TEMPLATE
     (e.g. `/api/planning/daily/{...}` style) rather than the raw URL, so high
     cardinality can't blow up the series. Exposed at `/metrics` (Prometheus
     text exposition format) and `/metrics.json`.

Because solver/LLM work happens inside the request handler, the per-endpoint
latency histogram doubles as solver-timing telemetry for free — e.g.
`http_request_duration_seconds` on `/api/planning/daily/generate`.

In-memory (single instance) by design; scrape it with Prometheus or just curl
`/metrics.json`. Env knobs (all optional):
  METRICS_ENABLED   "1" (default) / "0"   — record + expose request metrics
  LOG_JSON          "1" / "0" (default)    — emit JSON-formatted logs
  LOG_LEVEL         e.g. "INFO" (default)  — root log level when LOG_JSON is on
  LOG_ACCESS        "1" / "0" (default)    — emit a structured line per request
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

# Cumulative histogram buckets (seconds). The final +Inf bucket == total count.
_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Paths excluded from recording so a metrics scrape doesn't inflate its own
# series (and the bare liveness root stays quiet).
_SKIP_PATHS = {"/metrics", "/metrics.json"}


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def metrics_enabled() -> bool:
    return _truthy(os.getenv("METRICS_ENABLED", "1"))


# ───────────────────────────────────────────────────────────── metrics store
class MetricsRegistry:
    """Thread-safe in-process counters + latency histogram for HTTP requests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.in_flight = 0
        # (method, path, status) -> count
        self._requests: dict[tuple[str, str, str], int] = {}
        # (method, path) -> {"sum": float, "count": int, "buckets": [int,...]}
        self._durations: dict[tuple[str, str], dict] = {}

    def inc_in_flight(self, delta: int) -> None:
        with self._lock:
            self.in_flight = max(0, self.in_flight + delta)

    def record(self, method: str, path: str, status: int, duration_s: float) -> None:
        rkey = (method, path, str(status))
        dkey = (method, path)
        with self._lock:
            self._requests[rkey] = self._requests.get(rkey, 0) + 1
            d = self._durations.get(dkey)
            if d is None:
                d = {"sum": 0.0, "count": 0, "buckets": [0] * len(_BUCKETS)}
                self._durations[dkey] = d
            d["sum"] += duration_s
            d["count"] += 1
            for i, edge in enumerate(_BUCKETS):
                if duration_s <= edge:
                    d["buckets"][i] += 1

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._durations.clear()
            self.in_flight = 0
            self.start_time = time.time()

    def snapshot(self) -> dict:
        with self._lock:
            requests = dict(self._requests)
            durations = {k: {"sum": v["sum"], "count": v["count"], "buckets": list(v["buckets"])}
                         for k, v in self._durations.items()}
            in_flight = self.in_flight
            uptime = time.time() - self.start_time
        total = sum(requests.values())
        errors = sum(c for (m, p, s), c in requests.items() if s >= "500")
        return {
            "uptime_seconds": round(uptime, 1),
            "in_flight": in_flight,
            "requests_total": total,
            "errors_total": errors,
            "requests": [
                {"method": m, "path": p, "status": s, "count": c}
                for (m, p, s), c in sorted(requests.items())
            ],
            "latency": [
                {"method": m, "path": p, "count": d["count"],
                 "avg_ms": round(1000 * d["sum"] / d["count"], 1) if d["count"] else 0.0,
                 "sum_seconds": round(d["sum"], 4)}
                for (m, p), d in sorted(durations.items())
            ],
            "_raw_durations": durations,
        }


registry = MetricsRegistry()


def _esc(value: str) -> str:
    """Escape a Prometheus label value."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_prometheus() -> str:
    """Render the registry in Prometheus text exposition format."""
    snap = registry.snapshot()
    lines: list[str] = []

    lines.append("# HELP http_requests_total Total HTTP requests by method, route and status.")
    lines.append("# TYPE http_requests_total counter")
    for r in snap["requests"]:
        lines.append(
            f'http_requests_total{{method="{_esc(r["method"])}",'
            f'path="{_esc(r["path"])}",status="{_esc(r["status"])}"}} {r["count"]}'
        )

    lines.append("# HELP http_request_duration_seconds Request latency histogram.")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for (method, path), d in sorted(snap["_raw_durations"].items()):
        labels = f'method="{_esc(method)}",path="{_esc(path)}"'
        cumulative = 0
        for i, edge in enumerate(_BUCKETS):
            cumulative = d["buckets"][i]
            lines.append(f'http_request_duration_seconds_bucket{{{labels},le="{edge}"}} {cumulative}')
        lines.append(f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {d["count"]}')
        lines.append(f'http_request_duration_seconds_sum{{{labels}}} {round(d["sum"], 6)}')
        lines.append(f'http_request_duration_seconds_count{{{labels}}} {d["count"]}')

    lines.append("# HELP http_requests_in_flight In-flight HTTP requests right now.")
    lines.append("# TYPE http_requests_in_flight gauge")
    lines.append(f"http_requests_in_flight {snap['in_flight']}")

    lines.append("# HELP http_errors_total HTTP responses with status >= 500.")
    lines.append("# TYPE http_errors_total counter")
    lines.append(f"http_errors_total {snap['errors_total']}")

    lines.append("# HELP process_uptime_seconds Seconds since the metrics registry started.")
    lines.append("# TYPE process_uptime_seconds gauge")
    lines.append(f"process_uptime_seconds {snap['uptime_seconds']}")

    return "\n".join(lines) + "\n"


def render_json() -> dict:
    snap = registry.snapshot()
    snap.pop("_raw_durations", None)
    return snap


# ─────────────────────────────────────────────────────────── structured logs
class JsonLogFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object, including any `extra`
    fields attached to the record."""

    _RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"taskName"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger when LOG_JSON is truthy.
    No-op otherwise, so default human-readable logging is untouched."""
    if not _truthy(os.getenv("LOG_JSON")):
        return
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


_access_log = logging.getLogger("app.access")


def _route_template(request, fallback: str) -> str:
    """The matched route's path template (low cardinality), or a safe fallback."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "unmatched"


def install_observability(app) -> None:
    """Register the metrics middleware and the /metrics endpoints on the app."""
    configure_logging()

    @app.middleware("http")
    async def _observe(request, call_next):
        path = request.url.path
        if not metrics_enabled() or path in _SKIP_PATHS:
            return await call_next(request)
        registry.inc_in_flight(1)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            registry.inc_in_flight(-1)
            template = _route_template(request, path)
            registry.record(request.method, template, status, duration)
            if _truthy(os.getenv("LOG_ACCESS")):
                _access_log.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": template,
                        "status": status,
                        "duration_ms": round(duration * 1000, 1),
                    },
                )

    @app.get("/metrics", include_in_schema=False)
    async def metrics_text():
        from fastapi.responses import PlainTextResponse
        if not metrics_enabled():
            return PlainTextResponse("metrics disabled\n", status_code=503)
        return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")

    @app.get("/metrics.json", include_in_schema=False)
    async def metrics_json():
        from fastapi.responses import JSONResponse
        if not metrics_enabled():
            return JSONResponse({"detail": "metrics disabled"}, status_code=503)
        return JSONResponse(render_json())
