"""Metrics/KPI endpoints — reads from Coficab ERD via KpiService."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, get_db_optional
from app.services.auth_service import get_current_user
from app.services.kpi_service import KpiService

router = APIRouter()


@router.get("/kpi")
async def get_kpi(
    ref_date: Optional[date] = Query(None, description="Reference date (default: today)"),
    _user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Return the 8 official Coficab KPIs for the month containing ref_date.
    Each entry includes value, unit, color band, target, and month-over-month trend.
    """
    if not db:
        return {"kpis": []}
    svc = KpiService(db)
    kpis = svc.get_dashboard_kpis(ref_date)
    return {"kpis": kpis}


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
