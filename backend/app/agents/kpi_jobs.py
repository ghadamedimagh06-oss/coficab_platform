"""KPI snapshot jobs.

These jobs materialize the live KPI formulas into kpi_journalier and
kpi_mensuel so dashboard reads stay fast and stable.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.kpi import KpiDefinition, KpiJournalier, KpiMensuel, KpiStatus
from app.services.kpi_service import KPI_CODES_ORDERED, KpiService, compute_color

log = logging.getLogger(__name__)

DAILY_CODES = ["R4-06", "R4-02", "R4-13", "R4"]
MONTHLY_CODES = ["R4-02-PF", "R4-03", "R5-10", "R4-12"]


def run_daily(target: date | None = None, db: Session | None = None) -> int:
    """Upsert one daily snapshot row per available KPI definition."""
    target = target or (date.today() - timedelta(days=1))
    if db is None and not SessionLocal:
        log.warning("KPI daily job skipped: database is not available")
        return 0
    return _with_session(db, lambda session: _run_daily(session, target))


def run_monthly(year: int | None = None, month: int | None = None, db: Session | None = None) -> int:
    """Upsert one monthly snapshot row per available KPI definition."""
    if year is None or month is None:
        previous_month = date.today().replace(day=1) - timedelta(days=1)
        year = year or previous_month.year
        month = month or previous_month.month
    if db is None and not SessionLocal:
        log.warning("KPI monthly job skipped: database is not available")
        return 0
    return _with_session(db, lambda session: _run_monthly(session, year, month))


def recompute(start: date, end: date, db: Session | None = None) -> dict:
    """Backfill daily snapshots and monthly rollups for an inclusive date range."""
    if end < start:
        raise ValueError("end date must be on or after start date")
    if db is None and not SessionLocal:
        log.warning("KPI recompute skipped: database is not available")
        return {"daily_rows": 0, "monthly_rows": 0}

    def _work(session: Session) -> dict:
        daily_rows = 0
        day = start
        months: set[tuple[int, int]] = set()
        while day <= end:
            daily_rows += _run_daily(session, day, commit=False)
            months.add((day.year, day.month))
            day += timedelta(days=1)

        monthly_rows = 0
        for year, month in sorted(months):
            monthly_rows += _run_monthly(session, year, month, commit=False)
        session.commit()
        return {"daily_rows": daily_rows, "monthly_rows": monthly_rows}

    return _with_session(db, _work)


def _run_daily(db: Session, target: date, commit: bool = True) -> int:
    service = KpiService(db)
    month_start = target.replace(day=1)
    written = 0

    for code in _ordered_codes(DAILY_CODES + MONTHLY_CODES):
        start = target if code in DAILY_CODES else month_start
        value = service._compute_live(code, start, target)
        if _upsert_daily(db, code, target, value):
            written += 1

    if commit:
        db.commit()
    log.info("kpi_daily complete: %s rows for %s", written, target)
    return written


def _run_monthly(db: Session, year: int, month: int, commit: bool = True) -> int:
    service = KpiService(db)
    start, end = _month_bounds(year, month)
    written = 0

    for code in _ordered_codes(KPI_CODES_ORDERED):
        value = service._compute_live(code, start, end)
        if _upsert_monthly(db, code, year, month, value):
            written += 1

    if commit:
        db.commit()
    log.info("kpi_monthly complete: %s rows for %04d-%02d", written, year, month)
    return written


def _upsert_daily(db: Session, code: str, target: date, value: float | None) -> bool:
    definition = _definition(db, code)
    if definition is None:
        return False

    color = compute_color(definition, value) if value is not None else "grey"
    row = (
        db.query(KpiJournalier)
        .filter(
            KpiJournalier.kpi_def_id == definition.id,
            KpiJournalier.date_mesure == target,
            KpiJournalier.plant.is_(None),
        )
        .first()
    )
    if row is None:
        row = KpiJournalier(kpi_def_id=definition.id, date_mesure=target)
        db.add(row)

    row.valeur = value
    row.color = color
    return True


def _upsert_monthly(db: Session, code: str, year: int, month: int, value: float | None) -> bool:
    definition = _definition(db, code)
    if definition is None:
        return False

    color = compute_color(definition, value) if value is not None else "grey"
    row = (
        db.query(KpiMensuel)
        .filter(
            KpiMensuel.kpi_def_id == definition.id,
            KpiMensuel.annee == year,
            KpiMensuel.mois == month,
            KpiMensuel.plant.is_(None),
        )
        .first()
    )
    if row is None:
        row = KpiMensuel(kpi_def_id=definition.id, annee=year, mois=month)
        db.add(row)

    row.valeur = value
    row.target = definition.target_2025
    row.color = color
    row.status = _status_for(color)
    return True


def _definition(db: Session, code: str) -> KpiDefinition | None:
    return db.query(KpiDefinition).filter(KpiDefinition.code == code).first()


def _ordered_codes(codes: Iterable[str]) -> list[str]:
    wanted = set(codes)
    return [code for code in KPI_CODES_ORDERED if code in wanted]


def _status_for(color: str) -> KpiStatus:
    if color == "green":
        return KpiStatus.OK
    if color == "yellow":
        return KpiStatus.WARN
    if color == "red":
        return KpiStatus.ALERT
    return KpiStatus.NA


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return start, next_month - timedelta(days=1)


def _with_session(db: Session | None, work):
    if db is not None:
        return work(db)

    session = SessionLocal()
    try:
        return work(session)
    finally:
        session.close()
