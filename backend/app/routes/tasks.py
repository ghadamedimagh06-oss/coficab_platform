from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Dict

from app.database import get_db
from app.models.livraison import Livraison

router = APIRouter()


@router.post("/daily-planning")
async def daily_planning(db: Session = Depends(get_db)) -> Dict:
    """Activate today's deliveries and mark them as IN_EXECUTION.

    Returns number of deliveries activated.
    """
    today = date.today()
    # Match deliveries with delivery_date falling on today's date (ignoring time)
    deliveries = db.query(Livraison).filter(Livraison.delivery_date != None).all()
    activated = 0
    for d in deliveries:
        try:
            if d.delivery_date and d.delivery_date.date() == today:
                d.status = "IN_EXECUTION"
                db.add(d)
                activated += 1
        except Exception:
            continue
    db.commit()
    return {"status": "completed", "activated_deliveries": activated, "timestamp": datetime.utcnow().isoformat()}


@router.post("/process-data")
async def process_data():
    """Process ingested data (placeholder)."""
    return {"status": "completed", "records_processed": 150, "timestamp": datetime.utcnow().isoformat()}