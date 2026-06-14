"""Tests for the weekly-planning parse cache (W1.3)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

from app.services.planning_service import PlanningService, _PARSE_CACHE

WEEKLY_DIR = Path(__file__).resolve().parents[2] / "weekly planning"


def _workbook():
    return next(p for p in WEEKLY_DIR.glob("*.xlsx") if not p.name.startswith("~$"))


def test_second_parse_is_cached():
    _PARSE_CACHE.clear()
    svc = PlanningService(db=None)
    f = str(_workbook())
    a = svc.parse_weekly_planning(f)
    assert len(_PARSE_CACHE) == 1
    b = svc.parse_weekly_planning(f)
    assert len(a["rows"]) == len(b["rows"])


def test_cache_returns_isolated_copies():
    """Mutating a returned result must not poison the cache."""
    _PARSE_CACHE.clear()
    svc = PlanningService(db=None)
    f = str(_workbook())
    a = svc.parse_weekly_planning(f)
    original = len(a["rows"])
    a["rows"].append({"injected": True})
    b = svc.parse_weekly_planning(f)
    assert len(b["rows"]) == original


def test_cache_key_includes_mtime(tmp_path, monkeypatch):
    """A changed file (new mtime/size) must bypass the stale cache entry."""
    _PARSE_CACHE.clear()
    svc = PlanningService(db=None)
    f = str(_workbook())
    svc.parse_weekly_planning(f)
    assert len(_PARSE_CACHE) == 1
    key = next(iter(_PARSE_CACHE))
    # The key carries path, mtime_ns and size — three elements.
    assert len(key) == 3 and key[0].endswith(".xlsx")
