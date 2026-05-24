import os
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Optional
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent3_notifier")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


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
    logger.info(json.dumps({"agent": "agent3_notifier", "event": "publish", "channel": channel, "payload": payload, "timestamp": datetime.now().isoformat()}))
    try:
        redis_client.publish(channel, json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish to redis")


def build_alert(event_name: str, payload: dict) -> dict:
    alert = {
        "event": event_name,
        "summary": f"Agent3 Notifier received {event_name}",
        "payload": payload,
        "actions": [],
    }

    if event_name == "optimization_complete":
        status = payload.get("status", "unknown")
        alert["summary"] = f"Optimization complete: {status}"
        alert["actions"] = ["review routes", "notify operations team"]
    elif event_name == "post_deadline_modification":
        alert["summary"] = "Post-deadline modification detected"
        alert["actions"] = ["validate change", "check replanning need"]

    return alert


def handle_optimization_complete(payload: dict) -> None:
    alert = build_alert("optimization_complete", payload)
    logger.info(json.dumps({"agent": "agent3_notifier", "event": "alert", "alert": alert, "timestamp": datetime.now().isoformat()}))


def handle_deadline_modification(payload: dict) -> None:
    alert = build_alert("post_deadline_modification", payload)
    logger.info(json.dumps({"agent": "agent3_notifier", "event": "alert", "alert": alert, "timestamp": datetime.now().isoformat()}))

    reason = payload.get("reason", "unknown")
    if payload.get("severity") == "high" or payload.get("eta_delay_minutes", 0) >= 10:
        logger.info("Publishing replanning_requested due to post-deadline issue: %s", reason)
        publish_event("replanning_requested", {"reason": reason, "source": "agent3_notifier"})


def run_listener() -> None:
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(["optimization_complete", "post_deadline_modification"])
    logger.info(json.dumps({"agent": "agent3_notifier", "event": "subscribe", "channels": ["optimization_complete", "post_deadline_modification"], "timestamp": datetime.now().isoformat()}))

    for message in pubsub.listen():
        if message is None or message.get("type") != "message":
            continue

        channel = message["channel"]
        try:
            payload = json.loads(message["data"])
        except Exception:
            payload = {"raw": message["data"]}

        if channel == "optimization_complete":
            handle_optimization_complete(payload)
        elif channel == "post_deadline_modification":
            handle_deadline_modification(payload)


def main() -> None:
    logger.info(json.dumps({"agent": "agent3_notifier", "event": "start", "timestamp": datetime.now().isoformat()}))

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
                    self.wfile.write(json.dumps({"agent": "agent3_notifier", "status": "healthy", "uptime_seconds": uptime}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        server = HTTPServer(("0.0.0.0", 8003), HealthHandler)
        server.serve_forever()

    start_time = time.time()
    threading.Thread(target=_health_server, daemon=True).start()

    while True:
        try:
            run_listener()
        except Exception as exc:
            logger.exception("Redis listener crashed, restarting: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
