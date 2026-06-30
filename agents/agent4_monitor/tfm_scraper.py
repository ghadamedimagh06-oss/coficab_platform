"""Hardcoded TFM website scraper adapter for demo mode.

The real TFM portal is not available during the PFE demo, so this module keeps
the integration shape honest: Agent 4 calls a scraper-like adapter, receives
normalized tracking rows, and submits them through the same TFM ingestion path
the real scraper will use later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List


TFM_DEMO_PORTAL = "https://tfm.coficab.local/transport-monitoring"

_SCRAPED_ROWS: list[dict] = [
    {
        "transport_id": "mission-101",
        "mission_id": 101,
        "truck": "2282TU131",
        "driver": "Ala",
        "status": "in_transit",
        "location": {"lat": 36.7608, "lng": 10.1711},
        "eta_hours": 1.35,
        "distance_remaining": 42.0,
        "delay_minutes": 0,
        "next_stop": "AEC WIRING TECHNOLOGY SARL",
    },
    {
        "transport_id": "mission-102",
        "mission_id": 102,
        "truck": "9524TU238",
        "driver": "Bilel",
        "status": "delayed",
        "location": {"lat": 36.8612, "lng": 10.0924},
        "eta_hours": 2.1,
        "distance_remaining": 57.5,
        "delay_minutes": 28,
        "issue": "TFM portal shows ETA slipping after Mjez El Beb traffic",
        "next_stop": "COFICAB MED",
    },
    {
        "transport_id": "mission-103",
        "mission_id": 103,
        "truck": "5735TU217",
        "driver": "Hbib",
        "status": "at_customer",
        "location": {"lat": 35.8256, "lng": 10.6370},
        "eta_hours": 0.15,
        "distance_remaining": 3.2,
        "delay_minutes": 4,
        "next_stop": "LEONI SOUSSE",
    },
]


def scrape_tfm_tracking() -> Dict:
    """Return normalized rows as if they were scraped from the TFM portal."""
    scraped_at = datetime.now(timezone.utc).isoformat()
    items: List[Dict] = []
    for row in _SCRAPED_ROWS:
        items.append({
            **row,
            "id": row["transport_id"],
            "scraped_at": scraped_at,
            "source": "TFM_SCRAPER",
        })
    return {
        "portal": TFM_DEMO_PORTAL,
        "mode": "hardcoded_web_scrape",
        "scraped_at": scraped_at,
        "items": items,
    }
