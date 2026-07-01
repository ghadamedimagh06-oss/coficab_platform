"""Metrics/KPI endpoints — reads from Coficab ERD via KpiService."""
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_db_optional
from app.services.auth_service import get_current_user, require_role
from app.services.kpi_service import KpiService

router = APIRouter()


class KpiRecomputeRequest(BaseModel):
    start: date
    end: date


# Small TTL cache for the live KPI fallback so /kpi doesn't re-run the optimiser
# on every poll. Keyed by day; mirrors the daily dashboard's caching.
_LIVE_KPI_CACHE: dict[str, tuple] = {}
_LIVE_KPI_TTL_SECONDS = 120


def _live_plan_kpis(ref_date: Optional[date]) -> dict:
    """Single source of truth fallback: derive the headline KPIs directly from
    the day's generated plan — the SAME numbers the operations dashboard shows —
    so /api/metrics/kpi is never empty before monthly snapshots are computed.
    Adds a CO₂-saved card so the sustainability story rides on the main KPIs too.
    """
    import time
    from pathlib import Path
    from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig
    from app.services import dashboard_service

    day = ref_date or date.today()
    key = day.isoformat()
    now = time.time()
    cached = _LIVE_KPI_CACHE.get(key)
    if cached and now - cached[0] < _LIVE_KPI_TTL_SECONDS:
        return cached[1]

    try:
        # routes/metrics.py → parents[3] is the repo root (matches optimization.py).
        weekly_dir = Path(__file__).resolve().parents[3] / "weekly planning"
        # Straight-line matrix (no live OSRM call) keeps this live-KPI fallback
        # fast — it mirrors the dashboard endpoint, which also skips OSRM here.
        plan = DailyPlanBuilder(
            weekly_dir, cfg=DailyPlanConfig(prefer_ortools=True, use_osrm_road_matrix=False)
        ).build(day)
        kpis = dashboard_service.plan_kpis(plan)
        s = plan.get("sustainability", {})
        if s.get("co2_saved_kg") is not None:
            kpis.append({
                "code": "ESG-CO2", "id": "co2_saved", "label": "CO₂ Saved",
                "value": s.get("co2_saved_kg"), "unit": "kg", "target": None,
                "color": "green", "direction": "up", "icon": "leaf",
                "hint": f"{s.get('co2_saved_pct')}% vs manual baseline", "basis": "planned",
            })
        payload = {"kpis": kpis, "source": "live_plan", "day": key}
        if len(_LIVE_KPI_CACHE) > 16:
            _LIVE_KPI_CACHE.clear()
        _LIVE_KPI_CACHE[key] = (now, payload)
        return payload
    except Exception as exc:
        return {"kpis": [], "source": "none", "error": str(exc)}


@router.get("/kpi")
async def get_kpi(
    ref_date: Optional[date] = Query(None, description="Reference date (default: today)"),
    period: Literal["day", "week", "month", "year"] = Query("month"),
    _user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Return the headline Coficab KPIs. Prefers materialised ERD snapshots; when
    those are empty (snapshots not yet computed) it falls back to LIVE
    plan-derived KPIs — the same source the operations dashboard uses — so the
    cards are always real and consistent across the app. The `source` field says
    which path produced the numbers.
    """
    effective_date = ref_date or date.today()
    if period == "day":
        operational_start = effective_date
    elif period == "week":
        operational_start = effective_date - timedelta(days=effective_date.weekday())
    elif period == "year":
        operational_start = effective_date.replace(month=1, day=1)
    else:
        operational_start = effective_date.replace(day=1)
    period_payload = {
        "kind": period,
        "from": operational_start.isoformat(),
        "to": effective_date.isoformat(),
    }
    if db:
        svc = KpiService(db)
        kpis = svc.get_dashboard_kpis(ref_date)
        if any(item.get("value") is not None for item in kpis):
            return {
                "kpis": kpis,
                "operational": svc.get_operational_summary(operational_start, effective_date),
                "period": period_payload,
                "source": "snapshots",
            }
    fallback = _live_plan_kpis(ref_date)
    fallback["operational"] = (
        KpiService(db).get_operational_summary(operational_start, effective_date)
        if db else {}
    )
    fallback["period"] = period_payload
    return fallback


@router.get("/kpi/snapshot/daily")
async def get_daily_snapshot(
    snapshot_date: date = Query(..., alias="date"),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All materialized KPI values for one day."""
    from app.models.kpi import KpiDefinition, KpiJournalier

    rows = (
        db.query(KpiJournalier)
        .join(KpiDefinition)
        .filter(KpiJournalier.date_mesure == snapshot_date, KpiJournalier.plant.is_(None))
        .order_by(KpiDefinition.code)
        .all()
    )
    return {
        "date": snapshot_date.isoformat(),
        "kpis": [
            {
                "code": row.kpi_def.code,
                "label": row.kpi_def.nom,
                "value": float(row.valeur) if row.valeur is not None else None,
                "unit": row.kpi_def.unite,
                "color": row.color,
            }
            for row in rows
        ],
    }


@router.get("/kpi/snapshot/monthly")
async def get_monthly_snapshot(
    ym: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All materialized KPI values for one month (ym=YYYY-MM)."""
    from app.models.kpi import KpiDefinition, KpiMensuel

    year, month = (int(part) for part in ym.split("-", 1))
    rows = (
        db.query(KpiMensuel)
        .join(KpiDefinition)
        .filter(KpiMensuel.annee == year, KpiMensuel.mois == month, KpiMensuel.plant.is_(None))
        .order_by(KpiDefinition.code)
        .all()
    )
    return {
        "ym": ym,
        "kpis": [
            {
                "code": row.kpi_def.code,
                "label": row.kpi_def.nom,
                "value": float(row.valeur) if row.valeur is not None else None,
                "unit": row.kpi_def.unite,
                "target": float(row.target) if row.target is not None else None,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "color": row.color,
            }
            for row in rows
        ],
    }


@router.post("/kpi/recompute")
async def recompute_kpis(
    payload: KpiRecomputeRequest,
    _user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Backfill KPI daily and monthly snapshots for an inclusive range."""
    from app.agents.kpi_jobs import recompute

    try:
        result = recompute(payload.start, payload.end, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", **result}


@router.get("/kpi/{code}")
async def get_kpi_history(
    code: str,
    months: int = Query(12, ge=1, le=36),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Monthly history for a single KPI — for the analytics sparklines."""
    from app.models.kpi import KpiDefinition, KpiMensuel
    kd = db.query(KpiDefinition).filter(KpiDefinition.code == code.upper()).first()
    if not kd:
        raise HTTPException(status_code=404, detail=f"KPI '{code}' not found in catalog")

    today = date.today()
    rows = (
        db.query(KpiMensuel)
        .filter(KpiMensuel.kpi_def_id == kd.id)
        .order_by(KpiMensuel.annee.desc(), KpiMensuel.mois.desc())
        .limit(months)
        .all()
    )
    history = [
        {
            "year": r.annee,
            "month": r.mois,
            "value": float(r.valeur) if r.valeur is not None else None,
            "color": r.color,
            "target": float(r.target) if r.target is not None else None,
        }
        for r in reversed(rows)
    ]
    return {
        "code": kd.code,
        "label": kd.nom,
        "unit": kd.unite,
        "target_2025": float(kd.target_2025) if kd.target_2025 is not None else None,
        "history": history,
    }


@router.get("/deliveries/weekly")
async def get_weekly_deliveries(
    weeks: int = Query(8, ge=1, le=52),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Weekly delivery trend (total / delivered / on-time) for the dashboard bar chart."""
    svc = KpiService(db)
    return {"weeks": svc.get_weekly_delivery_trend(weeks)}


@router.get("/efficiency/distribution")
async def get_efficiency_distribution(
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load efficiency distribution across missions in the last 30 days."""
    svc = KpiService(db)
    return {"segments": svc.get_efficiency_distribution()}


@router.get("/carbon/history")
async def get_carbon_history(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    group_by: Literal["day", "week", "month"] = Query("week"),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fuel-derived carbon history with an explicit configurable factor."""
    end = to_date or date.today()
    start = from_date or (end - timedelta(days=365))
    if end < start:
        raise HTTPException(status_code=422, detail="to must be on or after from")
    if (end - start).days > 3660:
        raise HTTPException(status_code=422, detail="date range cannot exceed 10 years")
    try:
        return KpiService(db).get_carbon_history(start, end, group_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/timeline")
async def get_timeline(
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent events for the dashboard timeline."""
    from app.models.evenement import EvenementAlea
    events = (
        db.query(EvenementAlea)
        .order_by(EvenementAlea.date_evenement.desc())
        .limit(limit)
        .all()
    )
    return {
        "events": [
            {
                "id": e.id,
                "type": e.type,
                "description": e.description,
                "date": e.date_evenement.isoformat() if e.date_evenement else None,
                "resolu": e.resolu,
                "impact_delai_min": e.impact_delai_min,
            }
            for e in events
        ]
    }
