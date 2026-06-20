"""Tests for the request rate limiter (W4.4)."""

import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")


def test_fixed_window_counts_and_resets():
    from app.rate_limit import FixedWindowLimiter

    lim = FixedWindowLimiter()
    assert lim.allow("k", limit=2, window_s=60, now=1000)[0] is True
    assert lim.allow("k", limit=2, window_s=60, now=1000)[0] is True
    ok, retry = lim.allow("k", limit=2, window_s=60, now=1000)
    assert ok is False and retry > 0
    # A separate key has its own budget.
    assert lim.allow("other", limit=2, window_s=60, now=1000)[0] is True
    # New window resets the count.
    assert lim.allow("k", limit=2, window_s=60, now=1061)[0] is True


def test_disabled_by_default_in_tests(monkeypatch):
    # conftest sets RATE_LIMIT_ENABLED=0; the limiter must be a no-op.
    from app import rate_limit

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    assert rate_limit._enabled() is False


def test_middleware_returns_429_over_budget(monkeypatch):
    from app import rate_limit
    from fastapi.testclient import TestClient
    from app.main import app

    rate_limit._limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT", "3")

    client = TestClient(app)
    codes = [client.get("/").status_code for _ in range(6)]
    assert codes.count(200) <= 3
    assert 429 in codes

    rate_limit._limiter.reset()
