"""Lightweight, dependency-free request rate limiting.

The copilot and the daily planning endpoints can each trigger the OR-Tools
solver (seconds of CPU), so an unthrottled caller — or a tool-happy LLM loop —
could pin the backend. This adds a simple per-IP fixed-window limiter with a
tighter budget for the expensive endpoints.

In-memory (single-instance) by design; swap the store for Redis if the API is
ever horizontally scaled. Disabled in tests via RATE_LIMIT_ENABLED=0.

Env knobs (all optional):
  RATE_LIMIT_ENABLED   "1" (default) / "0"
  RATE_LIMIT_WINDOW    seconds per window (default 60)
  RATE_LIMIT_DEFAULT   max requests/window for normal endpoints (default 240)
  RATE_LIMIT_HEAVY     max requests/window for solver/LLM endpoints (default 20)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from fastapi.responses import JSONResponse

# Path fragments whose handlers re-run the optimizer or call the LLM.
_HEAVY_FRAGMENTS = (
    "/api/planning/daily/generate",
    "/api/planning/daily/pareto",
    "/api/planning/daily/stress-test",
    "/api/planning/daily/confidence",
    "/api/planning/daily/replan",
    "/api/planning/daily/dashboard",
    "/api/copilot/chat",
)


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _enabled() -> bool:
    # Default ON; tests set RATE_LIMIT_ENABLED=0.
    return _truthy(os.getenv("RATE_LIMIT_ENABLED", "1"))


def _window() -> int:
    try:
        return max(1, int(os.getenv("RATE_LIMIT_WINDOW", "60")))
    except ValueError:
        return 60


def _default_limit() -> int:
    try:
        return max(1, int(os.getenv("RATE_LIMIT_DEFAULT", "240")))
    except ValueError:
        return 240


def _heavy_limit() -> int:
    try:
        return max(1, int(os.getenv("RATE_LIMIT_HEAVY", "20")))
    except ValueError:
        return 20


def _is_heavy(path: str) -> bool:
    return any(frag in path for frag in _HEAVY_FRAGMENTS)


class FixedWindowLimiter:
    """Thread-safe fixed-window counter. `limit`/`window` are passed per call so
    the middleware can honour live env changes without rebuilding state."""

    def __init__(self) -> None:
        self._store: dict[object, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: object, limit: int, window_s: int, now: Optional[float] = None) -> tuple[bool, int]:
        now = time.time() if now is None else now
        with self._lock:
            start, count = self._store.get(key, (now, 0))
            if now - start >= window_s:
                start, count = now, 0
            count += 1
            self._store[key] = (start, count)
            if count <= limit:
                return True, 0
            return False, int(window_s - (now - start)) + 1

    def reset(self) -> None:
        with self._lock:
            self._store.clear()


_limiter = FixedWindowLimiter()


class LoginThrottle:
    """Tracks consecutive failed logins per (ip, username) and locks the key for
    the rest of the window once a threshold is hit — basic brute-force defence.
    A successful login clears the counter."""

    def __init__(self) -> None:
        self._fails: dict[object, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: object, max_fails: int, window_s: int, now: Optional[float] = None) -> tuple[bool, int]:
        now = time.time() if now is None else now
        with self._lock:
            entry = self._fails.get(key)
            if not entry:
                return False, 0
            start, count = entry
            if now - start >= window_s:
                self._fails.pop(key, None)
                return False, 0
            if count >= max_fails:
                return True, int(window_s - (now - start)) + 1
            return False, 0

    def record_failure(self, key: object, window_s: int, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            start, count = self._fails.get(key, (now, 0))
            if now - start >= window_s:
                start, count = now, 0
            self._fails[key] = (start, count + 1)

    def clear(self, key: object) -> None:
        with self._lock:
            self._fails.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()


login_throttle = LoginThrottle()


def login_lockout_enabled() -> bool:
    return _truthy(os.getenv("LOGIN_LOCKOUT_ENABLED", "1"))


def login_max_fails() -> int:
    try:
        return max(1, int(os.getenv("LOGIN_MAX_FAILS", "5")))
    except ValueError:
        return 5


def login_window() -> int:
    try:
        return max(1, int(os.getenv("LOGIN_WINDOW", "900")))
    except ValueError:
        return 900


def install_rate_limiting(app) -> None:
    """Register the rate-limit middleware on a FastAPI app."""

    @app.middleware("http")
    async def _rate_limit(request, call_next):
        if not _enabled():
            return await call_next(request)
        ip = request.client.host if request.client else "anonymous"
        path = request.url.path
        if _is_heavy(path):
            limit, bucket = _heavy_limit(), "heavy"
        else:
            limit, bucket = _default_limit(), "default"
        ok, retry_after = _limiter.allow((ip, bucket), limit, _window())
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded — please slow down and retry."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
