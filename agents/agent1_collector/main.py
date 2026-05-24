import os
import time
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import requests
import redis
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent1_collector")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
WATCH_FOLDER = os.environ.get("WATCH_FOLDER", "/data/watch")
SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}


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
    log_obj = {
        "agent": "agent1_collector",
        "event": "publish_event",
        "channel": channel,
        "payload": payload,
        "timestamp": datetime.now().isoformat()
    }
    logger.info(json.dumps(log_obj))
    try:
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.exception("Failed to publish to redis: %s", e)


def trigger_ingestion(file_path: str) -> bool:
    endpoint = f"{BACKEND_URL}/api/ingestion/trigger"
    payload = {
        "source": "excel_collector",
        "file_path": file_path,
        "filename": Path(file_path).name,
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        logger.info(json.dumps({
            "agent": "agent1_collector",
            "event": "ingestion_triggered",
            "file": Path(file_path).name,
            "timestamp": datetime.now().isoformat()
        }))
        return True
    except Exception as exc:
        logger.exception("Failed to trigger ingestion: %s", exc)
        return False


def process_file(file_path: str) -> None:
    if not Path(file_path).exists():
        logger.warning("File disappeared before processing: %s", file_path)
        return

    logger.info(json.dumps({
        "agent": "agent1_collector",
        "event": "process_file",
        "file": Path(file_path).name,
        "timestamp": datetime.now().isoformat()
    }))
    if trigger_ingestion(file_path):
        publish_event("data_ready", {"source": "excel_collector", "path": file_path})


class ExcelWatchHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            logger.info("Detected new Excel file: %s", path)
            time.sleep(2)
            process_file(str(path))


def scan_existing_files() -> None:
    folder = Path(WATCH_FOLDER)
    if not folder.exists():
        logger.warning(json.dumps({
            "agent": "agent1_collector",
            "event": "watch_folder_missing",
            "watch_folder": WATCH_FOLDER,
            "timestamp": datetime.now().isoformat()
        }))
        return

    for file_path in sorted(folder.iterdir()):
        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS and file_path.is_file():
            logger.info("Found existing Excel file: %s", file_path)
            process_file(str(file_path))


def main() -> None:
    logger.info(json.dumps({"agent": "agent1_collector", "event": "start", "timestamp": datetime.now().isoformat()}))
    scan_existing_files()

    observer = Observer()
    observer.schedule(ExcelWatchHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    # Start a minimal HTTP health server in background
    def _health_server():
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    uptime = int(time.time() - start_time)
                    self.wfile.write(json.dumps({"agent": "agent1_collector", "status": "healthy", "uptime_seconds": uptime}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        server = HTTPServer(("0.0.0.0", 8001), HealthHandler)
        server.serve_forever()

    start_time = time.time()
    threading.Thread(target=_health_server, daemon=True).start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info(json.dumps({"agent": "agent1_collector", "event": "stop", "timestamp": datetime.now().isoformat()}))
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
