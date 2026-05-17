"""
Data Routes for CofICab Platform
API endpoints for retrieving livraison and ingestion data
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
import datetime
from app.database import get_db_optional
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.services.ingestion_service import IngestionService

router = APIRouter()

@router.get("/transports")
async def get_transports(
    status: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Retrieve all livraisons/transports - public endpoint"""
    try:
        # If database is available, fetch real data
        if db:
            query = db.query(Livraison)

            # Apply filters if provided
            if status:
                query = query.filter(Livraison.status == status)

            # Get total count
            total = query.count()

            # Apply pagination
            livraisons = query.offset(offset).limit(limit).all()

            # Convert to response format
            transport_list = []
            for livraison in livraisons:
                transport_list.append({
                    "id": livraison.id,
                    "driver": livraison.driver,
                    "vehicle": livraison.vehicle,
                    "status": livraison.status,
                    "start_location": livraison.start_location,
                    "end_location": livraison.end_location,
                    "distance_km": livraison.distance_km,
                    "priority": livraison.priority,
                    "notes": livraison.notes,
                    "created_at": livraison.created_at.isoformat() if livraison.created_at else None
                })

            return {
                "transports": transport_list,
                "total": total
            }
        else:
            # Return mock data if database is unavailable
            return {
                "transports": [
                    {
                        "id": 1,
                        "driver": "John Smith",
                        "vehicle": "TRUCK-001",
                        "status": "in_transit",
                        "start_location": "Paris, FR",
                        "end_location": "Lyon, FR",
                        "distance_km": 465.5,
                        "priority": "normal",
                        "notes": None,
                        "created_at": "2026-05-06T10:00:00"
                    },
                    {
                        "id": 2,
                        "driver": "Marie Dupont",
                        "vehicle": "TRUCK-002",
                        "status": "completed",
                        "start_location": "Lyon, FR",
                        "end_location": "Marseille, FR",
                        "distance_km": 315.2,
                        "priority": "high",
                        "notes": "Urgent delivery",
                        "created_at": "2026-05-06T09:30:00"
                    }
                ],
                "total": 2
            }

    except Exception as e:
        # Return mock data on error
        return {
            "transports": [
                {
                    "id": 1,
                    "driver": "John Smith",
                    "vehicle": "TRUCK-001",
                    "status": "in_transit",
                    "start_location": "Paris, FR",
                    "end_location": "Lyon, FR",
                    "distance_km": 465.5,
                    "priority": "normal",
                    "notes": None,
                    "created_at": "2026-05-06T10:00:00"
                }
            ],
            "total": 1,
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