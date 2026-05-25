import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Optional
import requests
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent2_optimizer")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
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
    logger.info(json.dumps({"agent": "agent2_optimizer", "event": "publish", "channel": channel, "payload": payload, "timestamp": datetime.now().isoformat()}))
    try:
        redis_client.publish(channel, json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish to redis")


def optimize_planning(trigger: str, payload: dict) -> None:
    logger.info(json.dumps({"agent": "agent2_optimizer", "event": "optimize_trigger", "trigger": trigger, "payload": payload, "timestamp": datetime.now().isoformat()}))
    endpoint = f"{BACKEND_URL}/api/optimization/planning/generate"
    body = {"trigger": trigger, "context": payload}

    try:
        response = requests.post(endpoint, json=body, timeout=60)
        response.raise_for_status()
        logger.info("Optimization request succeeded for %s", trigger)
        publish_event("optimization_complete", {"trigger": trigger, "status": "success"})
    except Exception as exc:
        logger.error("Optimization request failed: %s", exc)
        publish_event("optimization_complete", {"trigger": trigger, "status": "failure", "error": str(exc)})


def run_listener() -> None:
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(["data_ready", "replanning_requested", "trigger_15h00"])
    logger.info(json.dumps({"agent": "agent2_optimizer", "event": "subscribe", "channels": ["data_ready", "replanning_requested", "trigger_15h00"], "timestamp": datetime.now().isoformat()}))

    for message in pubsub.listen():
        if message is None or message.get("type") != "message":
            continue

        channel = message["channel"]
        try:
            payload = json.loads(message["data"])
        except Exception:
            payload = {"raw": message["data"]}

        if channel in {"data_ready", "replanning_requested", "trigger_15h00"}:
            optimize_planning(channel, payload)


def main() -> None:
    logger.info(json.dumps({"agent": "agent2_optimizer", "event": "start", "timestamp": datetime.now().isoformat()}))

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
                    self.wfile.write(json.dumps({"agent": "agent2_optimizer", "status": "healthy", "uptime_seconds": uptime}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        server = HTTPServer(("0.0.0.0", 8002), HealthHandler)
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
