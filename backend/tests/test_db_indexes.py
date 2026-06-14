"""Tests for hot-path database indexes (W4.1).

Verifies create_all emits indexes on the FK/filter columns that the planning,
KPI and data queries hit, so they stay fast on Postgres as data grows.
"""

import os

import pytest
from sqlalchemy import create_engine, inspect

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")


@pytest.fixture(scope="module")
def inspector():
    from app.database import Base
    # Import the app so every model is registered on Base.metadata (some models,
    # e.g. Livraison, are only imported via their routers).
    import app.main  # noqa: F401

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return inspect(engine)


def _indexed_columns(inspector, table):
    cols = set()
    for ix in inspector.get_indexes(table):
        cols.update(ix.get("column_names") or [])
    return cols


@pytest.mark.parametrize(
    "table,column",
    [
        ("plan_mission", "plan_version_id"),
        ("plan_mission", "date_mission"),
        ("mission_demande", "mission_id"),
        ("mission_demande", "demande_id"),
        ("demandes_local", "client_id"),
        ("demandes_local", "date_livraison"),
        ("livraisons", "delivery_day"),
        ("livraisons", "status"),
        ("kpi_journalier", "kpi_def_id"),
        ("kpi_journalier", "date_mesure"),
    ],
)
def test_hot_column_is_indexed(inspector, table, column):
    assert column in _indexed_columns(inspector, table), (
        f"expected an index on {table}.{column}"
    )
