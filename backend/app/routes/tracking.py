from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
from datetime import datetime

from app.database import get_db
from app.models.transport_tracking import TransportTracking

router = APIRouter()


@router.get("/live")
async def get_live_tracking(db: Session = Depends(get_db)):
    """Return recent tracking records (last 100)."""
    records = db.query(TransportTracking).order_by(TransportTracking.id.desc()).limit(100).all()
    result = []
    for r in records:
        try:
            location = json.loads(r.location) if r.location else None
        except Exception:
            location = None
        result.append({
            "transport_id": r.transport_id,
            "status": r.status,
            "location": location,
            "eta_hours": r.eta_hours,
            "distance_remaining": r.distance_remaining,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        })
    return {"tracking_data": result, "count": len(result)}


@router.post("/sync")
async def sync_tracking(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Persist tracking sync payload into transport_tracking table.

    Expected payload: {"items": [{transport object}, ...], "source": "agent"}
    Returns: count of items stored.
    """
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Invalid payload: 'items' must be a list")

    stored = 0
    for item in items:
        try:
            transport_id = str(item.get("id") or item.get("transport_id") or "")
            status = item.get("status")
            location = item.get("location")
            eta = item.get("eta_hours") or item.get("eta")
            distance_remaining = item.get("distance_remaining") or item.get("distance") or item.get("distance_km")

            record = TransportTracking(
                transport_id=transport_id,
                status=status,
                location=json.dumps(location) if location is not None else None,
                eta_hours=float(eta) if eta is not None else None,
                distance_remaining=float(distance_remaining) if distance_remaining is not None else None,
                source=payload.get("source")
            )
            db.add(record)
            stored += 1
        except Exception:
            continue

    db.commit()
    return {"status": "synced", "count": stored, "timestamp": datetime.utcnow().isoformat()}