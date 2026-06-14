"""Tests for login brute-force lockout (W4.7)."""

import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")


def test_login_throttle_unit():
    from app.rate_limit import LoginThrottle

    t = LoginThrottle()
    key = ("1.2.3.4", "bob")
    # Under the threshold: not locked.
    for _ in range(3):
        assert t.is_locked(key, max_fails=3, window_s=900)[0] is False
        t.record_failure(key, window_s=900)
    # Reached the threshold: locked with a positive retry-after.
    locked, retry = t.is_locked(key, max_fails=3, window_s=900)
    assert locked is True and retry > 0
    # A success clears it.
    t.clear(key)
    assert t.is_locked(key, max_fails=3, window_s=900)[0] is False


def test_login_endpoint_locks_after_threshold(client, monkeypatch):
    from app import rate_limit

    rate_limit.login_throttle.reset()
    monkeypatch.setenv("LOGIN_LOCKOUT_ENABLED", "1")
    monkeypatch.setenv("LOGIN_MAX_FAILS", "3")

    body = {"username": "nobody", "password": "wrong"}
    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(5)]
    # First few are 401 (bad creds); once the threshold is hit it flips to 429.
    assert 401 in codes
    assert 429 in codes
    # Lockout must not precede the threshold.
    assert codes.index(429) >= 3

    rate_limit.login_throttle.reset()
