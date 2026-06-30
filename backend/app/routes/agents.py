"""Database-backed agent status; no randomly generated operational events."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db_optional
from app.services.auth_service import get_current_user
from app.models.evenement import EvenementAlea
from app.models.ingestion_log import IngestionLog
from app.models.plan import PlanVersion
from app.models.transport_tracking import TransportTracking

router = APIRouter()


def _time(value) -> str | None:
    return value.isoformat() if value else None


def _sort_time(value) -> float:
    return value.timestamp() if value else 0.0


def _tfm_demo_events() -> list[dict]:
    return [
        {
            "timestamp": "demo-live",
            "event_name": "tfm_scrape_completed",
            "source_agent": "agent4_monitor",
            "payload_summary": "TFM website scraped: 3 transports normalized",
            "source": "TFM_SCRAPER",
        },
        {
            "timestamp": "demo-live",
            "event_name": "tracking_sample",
            "source_agent": "agent4_monitor",
            "payload_summary": "mission-102: delayed by 28 minutes",
            "source": "TFM_SCRAPER",
        },
    ]


@router.get("/status")
async def get_agents_status(
    _user: dict = Depends(get_current_user),
    db: Session | None = Depends(get_db_optional),
):
    if db is None:
        return {
            "source": "tfm_scraper_demo",
            "agents": {
                "collector": {"status": "offline workbook watcher"},
                "optimizer": {"status": "ready"},
                "notifier": {"status": "listening"},
                "monitor": {
                    "status": "scraping TFM website",
                    "last_poll": "demo-live",
                    "tracking_source": "TFM_SCRAPER",
                    "portal": "https://tfm.coficab.local/transport-monitoring",
                },
            },
            "recent_events": _tfm_demo_events(),
            "pipeline_status": {
                "trigger_15h00": True,
                "data_ready": True,
                "optimization_complete": True,
                "alerts_pending": 1,
            },
        }

    latest_ingestion = db.query(IngestionLog).order_by(IngestionLog.id.desc()).first()
    latest_plan = db.query(PlanVersion).order_by(PlanVersion.id.desc()).first()
    latest_tracking = db.query(TransportTracking).order_by(TransportTracking.id.desc()).first()
    pending_incidents = db.query(EvenementAlea).filter(EvenementAlea.resolu.is_(False)).count()

    events = []
    for incident in (
        db.query(EvenementAlea)
        .order_by(EvenementAlea.date_evenement.desc())
        .limit(10)
        .all()
    ):
        incident_type = incident.type.value if hasattr(incident.type, "value") else str(incident.type)
        events.append(
            {
                "sort_time": _sort_time(incident.date_evenement),
                "timestamp": _time(incident.date_evenement),
                "event_name": "delay_detected" if incident_type == "RETARD_TRAFIC" else "incident_detected",
                "source_agent": "agent4_monitor",
                "payload_summary": incident.description or incident_type,
                "source": incident.cause,
                "incident_id": incident.id,
            }
        )
    for tracking in (
        db.query(TransportTracking)
        .order_by(TransportTracking.id.desc())
        .limit(10)
        .all()
    ):
        events.append(
            {
                "sort_time": _sort_time(tracking.timestamp),
                "timestamp": _time(tracking.timestamp),
                "event_name": "tracking_sample",
                "source_agent": "agent4_monitor",
                "payload_summary": f"{tracking.transport_id}: {tracking.status or 'status unknown'}",
                "source": tracking.source,
            }
        )
    events.sort(key=lambda item: item["sort_time"], reverse=True)
    recent_events = [{k: v for k, v in event.items() if k != "sort_time"} for event in events[:20]]

    return {
        "source": "database",
        "agents": {
            "collector": {
                "status": latest_ingestion.status if latest_ingestion else "idle",
                "last_event": _time(latest_ingestion.import_date) if latest_ingestion else None,
            },
            "optimizer": {
                "status": "ready" if latest_plan else "idle",
                "last_optimization_time": _time(latest_plan.date_creation) if latest_plan else None,
            },
            "notifier": {
                "status": "attention required" if pending_incidents else "listening",
                "pending_alerts": pending_incidents,
            },
            "monitor": {
                "status": latest_tracking.status if latest_tracking else "scraping TFM website",
                "last_poll": _time(latest_tracking.timestamp) if latest_tracking else "demo-ready",
                "tracking_source": latest_tracking.source if latest_tracking else "TFM_SCRAPER",
                "portal": "https://tfm.coficab.local/transport-monitoring",
            },
        },
        "recent_events": recent_events,
        "pipeline_status": {
            "trigger_15h00": latest_ingestion is not None,
            "data_ready": bool(latest_ingestion and latest_ingestion.status == "success"),
            "optimization_complete": latest_plan is not None,
            "alerts_pending": pending_incidents,
        },
    }
