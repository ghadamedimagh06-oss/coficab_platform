from fastapi import APIRouter
from datetime import datetime, timedelta

router = APIRouter()

START_TIME = datetime.now()

BASE_EVENTS = [
    {
        "event_name": "data_ready",
        "source_agent": "agent1_collector",
        "payload_summary": "file: planning_J1.xlsx",
    },
    {
        "event_name": "trigger_15h00",
        "source_agent": "orchestrator",
        "payload_summary": "scheduled trigger",
    },
    {
        "event_name": "optimization_complete",
        "source_agent": "agent2_optimizer",
        "payload_summary": "12 routes generated",
    },
    {
        "event_name": "alert_sent",
        "source_agent": "agent3_notifier",
        "payload_summary": "modification detected",
    },
]


def _format_time(value: datetime) -> str:
    return value.strftime("%H:%M:%S")


def _build_recent_events() -> list[dict]:
    now = datetime.now()
    events = []
    offset = 0
    for event_template in BASE_EVENTS:
        event_time = now - timedelta(seconds=offset)
        events.append({
            "timestamp": _format_time(event_time),
            "event_name": event_template["event_name"],
            "source_agent": event_template["source_agent"],
            "payload_summary": event_template["payload_summary"],
        })
        offset += 7

    cycle = now.second % 30
    if cycle < 8:
        events.insert(0, {
            "timestamp": _format_time(now),
            "event_name": "post_deadline_modification",
            "source_agent": "agent3_notifier",
            "payload_summary": "client: ACME Industries — modification after 15h00",
        })
    elif cycle < 16:
        events.insert(0, {
            "timestamp": _format_time(now),
            "event_name": "delay_detected",
            "source_agent": "agent4_monitor",
            "payload_summary": "delivery late by 12 min",
        })
    else:
        events.insert(0, {
            "timestamp": _format_time(now),
            "event_name": "watchdog_scan",
            "source_agent": "agent1_collector",
            "payload_summary": "new file found in shared folder",
        })

    return events[:20]


@router.get("/status")
async def get_agents_status():
    """Return a simulated agent status dashboard feed."""
    now = datetime.now()
    cycle = now.second % 36
    collector_status = "watching" if cycle < 10 else "processing" if cycle < 22 else "idle"
    optimizer_status = "optimizing" if cycle < 12 else "done" if cycle < 26 else "idle"
    notifier_status = "alert sent" if cycle % 20 < 6 else "listening"
    monitor_status = "delay detected" if cycle % 18 < 5 else "polling"

    pending_alerts = 1 if cycle % 25 < 8 else 0
    last_opt_time = now - timedelta(minutes=(cycle % 10) + 1)
    last_poll_time = now - timedelta(seconds=5 + (cycle % 10))

    recent_events = _build_recent_events()
    pipeline_status = {
        "trigger_15h00": cycle >= 5,
        "data_ready": cycle >= 12,
        "optimization_complete": cycle >= 20,
        "alerts_pending": pending_alerts,
    }

    return {
        "agents": {
            "collector": {
                "status": collector_status,
                "last_event": recent_events[0]["event_name"],
                "uptime": int((now - START_TIME).total_seconds()),
            },
            "optimizer": {
                "status": optimizer_status,
                "last_optimization_time": _format_time(last_opt_time),
                "uptime": int((now - START_TIME).total_seconds()),
            },
            "notifier": {
                "status": notifier_status,
                "pending_alerts": pending_alerts,
                "uptime": int((now - START_TIME).total_seconds()),
            },
            "monitor": {
                "status": monitor_status,
                "last_poll": _format_time(last_poll_time),
                "uptime": int((now - START_TIME).total_seconds()),
            },
        },
        "recent_events": recent_events,
        "pipeline_status": pipeline_status,
    }
