"""
Data Routes for CofICab Platform
API endpoints for retrieving livraison and ingestion data
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import datetime
from pathlib import Path
import pandas as pd
from app.database import get_db_optional
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.services.ingestion_service import IngestionService
from app.services.planning_service import PlanningService
from app.data.synthetic_daily_planning import MOCK_TRANSPORTS

router = APIRouter()

# Prefer explicit environment configuration, otherwise fall back to the user's local Excel file if present.
env_weekly_file = os.getenv("WEEKLY_PLANNING_FILE_PATH")
if env_weekly_file:
    WEEKLY_PLANNING_FILE = Path(env_weekly_file).resolve()
else:
    default_local_file = Path(r"C:\Users\USER\OneDrive\Desktop\coficab\DB\weekly planning\Weekly Delivery planning W0526.xlsx")
    repo_default_file = Path(__file__).resolve().parents[3] / "weekly planning" / "Weekly Delivery planning W0526.xlsx"
    if default_local_file.exists():
        WEEKLY_PLANNING_FILE = default_local_file
    else:
        WEEKLY_PLANNING_FILE = repo_default_file


def _load_weekly_planning_transports(status: Optional[str] = None, day: Optional[str] = None, limit: int = 100, offset: int = 0):
    if WEEKLY_PLANNING_FILE.exists():
        try:
            service = PlanningService(db=None)
            plan_data = service.parse_weekly_planning(str(WEEKLY_PLANNING_FILE))
            rows = plan_data["rows"]
            if status:
                rows = [row for row in rows if (row.get("status") or "pending") == status]
            if day:
                rows = [row for row in rows if row.get("delivery_day") == day]
            total = len(rows)
            paginated = rows[offset: offset + limit]
            transports = []
            for row in paginated:
                transports.append({
                    "id": row.get("row_number"),
                    "row_number": row.get("row_number"),
                    "delivery_day": row.get("delivery_day"),
                    "delivery_date": row.get("delivery_date").isoformat() if row.get("delivery_date") else None,
                    "client": row.get("client"),
                    "driver": row.get("driver"),
                    "vehicle": row.get("vehicle"),
                    "etd": row.get("etd"),
                    "eta": row.get("eta"),
                    "quantity": row.get("quantity"),
                    "start_location": row.get("start_location"),
                    "end_location": row.get("end_location"),
                    "distance_km": row.get("distance_km"),
                    "status": row.get("status") or "pending",
                    "priority": row.get("priority") or "normal",
                    "notes": row.get("notes"),
                    "created_at": None,
                })
            return transports, total
        except Exception:
            pass

    mock = MOCK_TRANSPORTS
    if status:
        mock = [t for t in mock if t.get("status") == status]
    if day:
        mock = [t for t in mock if t.get("delivery_day") == day]
    total = len(mock)
    return mock[offset: offset + limit], total

@router.get("/transports")
async def get_transports(
    status: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    force_file: Optional[bool] = Query(False),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Retrieve all livraisons/transports - public endpoint"""
    try:
        # If `force_file` requested, return parsed Excel/mock data regardless of DB
        if force_file:
            transports, total = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
            return {"transports": transports, "total": total}

        # If database is available, fetch real data
        if db:
            query = db.query(Livraison)

            # Apply filters if provided
            if status:
                query = query.filter(Livraison.status == status)
            if day:
                query = query.filter(Livraison.delivery_day == day)

            # Get total count
            total = query.count()

            # Apply pagination
            livraisons = query.offset(offset).limit(limit).all()

            # Convert to response format
            transport_list = []
            for livraison in livraisons:
                transport_list.append({
                    "id": livraison.id,
                    "row_number": livraison.row_number,
                    "delivery_day": livraison.delivery_day,
                    "delivery_date": livraison.delivery_date.isoformat() if livraison.delivery_date else None,
                    "client": livraison.client,
                    "driver": livraison.driver,
                    "vehicle": livraison.vehicle,
                    "etd": livraison.etd,
                    "eta": livraison.eta,
                    "quantity": livraison.quantity,
                    "start_location": livraison.start_location,
                    "end_location": livraison.end_location,
                    "distance_km": livraison.distance_km,
                    "status": livraison.status,
                    "priority": livraison.priority,
                    "notes": livraison.notes,
                    "created_at": livraison.created_at.isoformat() if livraison.created_at else None
                })

            return {
                "transports": transport_list,
                "total": total
            }
        else:
            transports, total = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
            return {"transports": transports, "total": total}

    except Exception as e:
        # Return file-based or mock data on error
        transports, total = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
        return {
            "transports": transports,
            "total": total,
            "error": f"Database error: {str(e)}"
        }

@router.get("/ingestion-history")
async def get_ingestion_history(
    limit: int = Query(50),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Get ingestion processing history"""
    try:
        if db:
            ingestion_service = IngestionService(db)
            history = ingestion_service.get_ingestion_history(limit)
            return {"history": history}
        else:
            return {
                "history": [
                    {
                        "id": 1,
                        "file_name": "weekly_planning.xlsx",
                        "import_date": "2026-05-06T10:00:00",
                        "status": "success",
                        "inserted_rows": 25,
                        "total_rows": 25,
                        "error_message": None
                    }
                ]
            }
    except Exception as e:
        return {
            "history": [],
            "error": f"Failed to retrieve history: {str(e)}"
        }

@router.get("/stats")
async def get_data_stats(db: Optional[Session] = Depends(get_db_optional)):
    """Get data statistics"""
    try:
        if db:
            # Count livraisons by status
            status_counts = {}
            for status in ["pending", "in_transit", "completed"]:
                count = db.query(Livraison).filter(Livraison.status == status).count()
                status_counts[status] = count

            # Total livraisons
            total_livraisons = db.query(Livraison).count()

            # Recent imports
            recent_imports = db.query(IngestionLog).filter(
                IngestionLog.status == "success"
            ).order_by(IngestionLog.import_date.desc()).limit(5).all()

            return {
                "total_livraisons": total_livraisons,
                "status_breakdown": status_counts,
                "recent_imports": len(recent_imports),
                "last_import": recent_imports[0].import_date.isoformat() if recent_imports else None
            }
        else:
            return {
                "total_livraisons": 2,
                "status_breakdown": {"pending": 0, "in_transit": 1, "completed": 1},
                "recent_imports": 1,
                "last_import": "2026-05-06T10:00:00"
            }
    except Exception as e:
        return {
            "total_livraisons": 0,
            "status_breakdown": {"pending": 0, "in_transit": 0, "completed": 0},
            "recent_imports": 0,
            "error": f"Failed to get stats: {str(e)}"
        }