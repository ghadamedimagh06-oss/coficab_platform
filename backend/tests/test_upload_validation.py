"""Tests for upload hardening on /api/ingestion/upload (W4.6)."""

import os

import pytest

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")

UPLOAD = "/api/ingestion/upload"
_XLSX_MAGIC = b"PK\x03\x04"


def test_rejects_non_xlsx_extension(client):
    r = client.post(UPLOAD, files={"file": ("data.csv", b"a,b,c", "text/csv")})
    assert r.status_code == 400
    assert ".xlsx" in r.json()["detail"]


def test_rejects_bad_magic_bytes(client):
    # .xlsx name but the content is not a ZIP/xlsx container.
    r = client.post(UPLOAD, files={"file": ("fake.xlsx", b"this is not a workbook", "application/octet-stream")})
    assert r.status_code == 400
    assert "valid .xlsx" in r.json()["detail"]


def test_rejects_oversized_file(client, monkeypatch):
    from app.routes import ingestion

    monkeypatch.setattr(ingestion, "MAX_UPLOAD_MB", 0)  # any non-empty file is too big
    content = _XLSX_MAGIC + b"\x00" * 100
    r = client.post(UPLOAD, files={"file": ("big.xlsx", content, "application/octet-stream")})
    assert r.status_code == 413


def test_rejects_wrong_content_type(client):
    r = client.post(UPLOAD, files={"file": ("x.xlsx", _XLSX_MAGIC, "image/png")})
    assert r.status_code == 400
