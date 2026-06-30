import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
import requests
import redis
from tfm_scraper import scrape_tfm_tracking

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent4_monitor")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
TFM_API_URL = os.environ.get("TFM_API_URL", "").strip()
TFM_INGEST_API_KEY = os.environ.get("TFM_INGEST_API_KEY", "demo-tfm-key").strip()
TFM_SCRAPE_MODE = os.environ.get("TFM_SCRAPE_MODE", "demo").strip().lower()
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
DELAY_THRESHOLD = int(os.environ.get("DELAY_THRESHOLD_MINUTES", "10"))


def get_redis_client():
    for attempt in range(5):
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            return client
        except Exception:
            wait = 2 ** attempt
            logger.warning("Redis connection failed, retrying in %ss", wait)
            time.sleep(wait)
    raise ConnectionError("Redis unavailable after 5 attempts")


redis_client = get_redis_client()


def publish_event(channel: str, payload: Optional[Dict] = None) -> None:
    payload = payload or {}
    logger.info(json.dumps({"agent": "agent4_monitor", "event": "publish", "channel": channel, "payload": payload, "timestamp": datetime.now().isoformat()}))
    try:
        redis_client.publish(channel, json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish to redis")


def get_tracking_status() -> List[Dict]:
    if TFM_SCRAPE_MODE == "demo" or not TFM_API_URL:
        payload = scrape_tfm_tracking()
        logger.info(json.dumps({
            "agent": "agent4_monitor",
            "event": "tfm_scrape_completed",
            "mode": payload["mode"],
            "portal": payload["portal"],
            "count": len(payload["items"]),
            "timestamp": payload["scraped_at"],
        }))
        return payload["items"]

    endpoints = [
        TFM_API_URL.rstrip("/"),
        f"{TFM_API_URL.rstrip('/')}/tracking",
        f"{TFM_API_URL.rstrip('/')}/api/tracking",
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=20)
            response.raise_for_status()
            payload = response.json()
            items = extract_tracking_items(payload)
            if items:
                return items
        except Exception as exc:
            logger.debug("Tracking endpoint failed %s: %s", endpoint, exc)

    return []


def extract_tracking_items(payload) -> List[Dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("tracking_data", "items", "transports", "data", "vehicles"):
        value = payload.get(key)
        if isinstance(value, dict):
            return [item for item in value.values() if isinstance(item, dict)]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    active = payload.get("active_missions")
    if isinstance(active, list):
        return [
            {
                "id": item.get("id"),
                "transport_id": item.get("id"),
                "status": item.get("status"),
                "eta": item.get("next_eta"),
                "distance_remaining": None,
                "location": item.get("location"),
            }
            for item in active
            if isinstance(item, dict)
        ]
    return []


def sync_tracking_payload(payload: dict) -> None:
    endpoint = f"{BACKEND_URL}/api/tracking/tfm/sync"
    try:
        if not TFM_INGEST_API_KEY:
            raise RuntimeError("TFM_INGEST_API_KEY is required for TFM ingestion")
        payload = {**payload, "source": "TFM_SCRAPER"}
        response = requests.post(
            endpoint,
            json=payload,
            headers={"X-TFM-Key": TFM_INGEST_API_KEY},
            timeout=20,
        )
        response.raise_for_status()
        logger.info(json.dumps({"agent": "agent4_monitor", "event": "sync_submitted", "count": len(payload.get("items", [])), "timestamp": datetime.now().isoformat()}))
    except Exception as exc:
        logger.exception("Tracking sync failed: %s", exc)


def detect_issues(items: list[dict]) -> None:
    modifications = []
    for item in items:
        delay = int(item.get("delay_minutes", 0) or 0)
        if delay >= DELAY_THRESHOLD:
            modifications.append({
                "transport_id": item.get("id"),
                "eta_delay_minutes": delay,
                "severity": "high" if delay >= DELAY_THRESHOLD else "medium",
                "reason": item.get("issue") or "delay detected",
            })

    if modifications:
        publish_event("post_deadline_modification", {"modifications": modifications, "source": "agent4_monitor"})


def main() -> None:
    logger.info(json.dumps({"agent": "agent4_monitor", "event": "start", "timestamp": datetime.now().isoformat()}))

    # start health server
    def _health_server():
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    uptime = int(time.time() - start_time)
                    self.wfile.write(json.dumps({"agent": "agent4_monitor", "status": "healthy", "uptime_seconds": uptime}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        server = HTTPServer(("0.0.0.0", 8004), HealthHandler)
        server.serve_forever()

    start_time = time.time()
    threading.Thread(target=_health_server, daemon=True).start()

    while True:
        try:
            transports = get_tracking_status()
            if transports:
                detect_issues(transports)
                sync_tracking_payload({"items": transports})
        except Exception as exc:
            logger.exception("Monitor loop exception: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
