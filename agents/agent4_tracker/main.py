"""
Agent 4 - TFM Tracker (Real-Time Tracking)

Polls TFM system every 5 minutes.
Calculates ETA and transport status.
Updates real-time data.

Role: Live tracking & visibility
"""

import os
import time
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
TFM_API_URL = os.getenv("TFM_API_URL", "http://tfm-api:8080")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))  # 5 minutes in seconds


class TFMTracker:
    """Tracks real-time transport status from TFM system."""

    def __init__(self):
        self.tracked_transports = {}
        self.last_poll_time = None

    def fetch_tfm_data(self):
        """Fetch transport data from TFM system."""
        try:
            response = requests.get(
                f"{TFM_API_URL}/api/transports",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"[TRACKER] TFM API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[TRACKER] Failed to fetch TFM data: {e}")
            return None

    def calculate_eta(self, transport_data):
        """Calculate ETA based on transport data."""
        try:
            # Simplified ETA calculation
            distance = transport_data.get("distance", 0)
            avg_speed = transport_data.get("avg_speed", 80)  # km/h
            hours_remaining = distance / avg_speed if avg_speed > 0 else 0
            return hours_remaining
        except Exception as e:
            logger.error(f"[TRACKER] ETA calculation failed: {e}")
            return None

    def update_tracking(self, transport_id, transport_data):
        """Update tracking information for a transport."""
        eta = self.calculate_eta(transport_data)
        
        tracking_record = {
            "transport_id": transport_id,
            "status": transport_data.get("status", "unknown"),
            "location": transport_data.get("location", {}),
            "eta_hours": eta,
            "distance_remaining": transport_data.get("distance", 0),
            "timestamp": datetime.now().isoformat()
        }
        
        self.tracked_transports[transport_id] = tracking_record
        logger.info(f"[TRACKER] Updated transport {transport_id}: ETA {eta:.1f}h")
        return tracking_record

    def sync_to_backend(self):
        """Sync all tracking data to backend."""
        try:
            response = requests.post(
                f"{BACKEND_API_URL}/api/tracking/sync",
                json=self.tracked_transports,
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"[TRACKER] Synced {len(self.tracked_transports)} transports")
                return True
            else:
                logger.error(f"[TRACKER] Sync failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[TRACKER] Failed to sync data: {e}")
            return False

    def poll_and_track(self):
        """Poll TFM system and update tracking data."""
        logger.info(f"[TRACKER] Polling TFM system at {datetime.now().isoformat()}")
        
        tfm_data = self.fetch_tfm_data()
        if tfm_data is None:
            logger.warning("[TRACKER] No data from TFM system")
            return
        
        # Process each transport
        for transport in tfm_data.get("transports", []):
            transport_id = transport.get("id")
            if transport_id:
                self.update_tracking(transport_id, transport)
        
        # Sync to backend
        self.sync_to_backend()
        self.last_poll_time = datetime.now()


def start_tracker():
    """Start continuous TFM tracking."""
    tracker = TFMTracker()
    logger.info(f"[TRACKER] Started with {POLL_INTERVAL}s poll interval")
    
    try:
        while True:
            tracker.poll_and_track()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        logger.info("[TRACKER] Stopped")


if __name__ == "__main__":
    start_tracker()
