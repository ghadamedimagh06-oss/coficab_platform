from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Dict
import datetime

from app.database import get_db_optional
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter()


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_optional)) -> str:
    if not db:
        raise HTTPException(status_code=401, detail="Unauthorized")
    auth_service = AuthService(db)
    username = auth_service.get_current_username(token)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return username


@router.get("/kpi")
async def get_kpi(current_user: str = Depends(get_current_user), db: Session = Depends(get_db_optional)) -> Dict:
    """Return KPIs calculated from database tables.

    - otif: percentage of completed deliveries
    - fill_rate: average quantity normalized to max observed quantity
    - delay_count: deliveries mentioning delays or priority urgent
    - planning_time: average ingestion processing time in seconds
    """
    if not db:
        return {"otif": 0.0, "fill_rate_percent": 0.0, "delay_count": 0, "planning_time_seconds": 0}

    # Total and completed deliveries
    total = db.query(func.count(Livraison.id)).scalar() or 0
    completed = db.query(func.count(Livraison.id)).filter(func.lower(Livraison.status) == "completed").scalar() or 0
    otif = round((completed / total * 100) if total > 0 else 0.0, 1)

    # Fill rate: average quantity normalized to max observed quantity
    avg_q = db.query(func.avg(Livraison.quantity)).scalar() or 0
    max_q = db.query(func.max(Livraison.quantity)).scalar() or 0
    fill_rate_percent = round(((avg_q / max_q) * 100) if (max_q and avg_q) else 0.0, 1)

    # Delay count heuristic: notes contain 'delay' or priority is 'urgent'
    delay_count = db.query(func.count(Livraison.id)).filter(
        or_(Livraison.notes.ilike("%delay%"), func.lower(Livraison.priority) == "urgent")
    ).scalar() or 0

    # Planning time: average (processed_at - import_date) in seconds for successful ingestions
    processed_rows = db.query(IngestionLog).filter(IngestionLog.status == "success", IngestionLog.processed_at.isnot(None)).all()
    total_seconds = 0
    samples = 0
    for r in processed_rows:
        if r.processed_at and r.import_date:
            diff = (r.processed_at - r.import_date).total_seconds()
            total_seconds += diff
            samples += 1
    planning_time_seconds = int(total_seconds / samples) if samples else 0

    return {
        "otif": otif,
        "fill_rate_percent": fill_rate_percent,
        "delay_count": int(delay_count),
        "planning_time_seconds": planning_time_seconds,
    }