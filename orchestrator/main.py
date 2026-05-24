import os
import time
import json
import subprocess
import threading
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
import redis
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Scheduler settings are handled by APScheduler/CronTrigger

# Use absolute paths for agent entrypoints so orchestrator can start them reliably
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = {
    "collector": ["python", os.path.join(BASE, "agents/agent1_collector/main.py")],
    "optimizer": ["python", os.path.join(BASE, "agents/agent2_optimizer/main.py")],
    "notifier": ["python", os.path.join(BASE, "agents/agent3_notifier/main.py")],
    "monitor": ["python", os.path.join(BASE, "agents/agent4_monitor/main.py")],
}

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
processes: Dict[str, Dict[str, Any]] = {}
last_events: Dict[str, str] = {}

app = FastAPI(title="CofICab Orchestrator")


def publish_event(channel: str, payload: Optional[Dict] = None) -> None:
    payload = payload or {}
    logger.info("Orchestrator publish %s: %s", channel, payload)
    try:
        redis_client.publish(channel, json.dumps(payload))
        last_events[channel] = json.dumps(payload)
    except Exception as e:
        logger.exception("Failed to publish event %s: %s", channel, e)


def start_agent(name: str, command: list[str]) -> None:
    if name in processes and processes[name]["process"].poll() is None:
        logger.info("Agent %s already running", name)
        return

    logger.info("Starting agent %s", name)
    proc = subprocess.Popen(command, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    processes[name] = {"process": proc, "command": command, "start_time": time.time()}

    def log_output():
        assert proc.stdout is not None
        for line in proc.stdout:
            logger.info("%s | %s", name, line.rstrip())

    threading.Thread(target=log_output, daemon=True).start()


def restart_agent(name: str) -> None:
    logger.warning("Restarting agent %s", name)
    proc = processes[name]["process"]
    try:
        proc.kill()
    except Exception:
        pass
    start_agent(name, processes[name]["command"])


def monitor_agents() -> None:
    while True:
        for name, info in list(processes.items()):
            proc = info["process"]
            if proc.poll() is not None:
                logger.warning("Agent %s exited with %s", name, proc.returncode)
                restart_agent(name)
        time.sleep(10)


def schedule_with_apscheduler(scheduler: BackgroundScheduler) -> None:
    """Register scheduled jobs using APScheduler CronTriggers."""

    def job_1500():
        publish_event("trigger_15h00", {"scheduled": True})

    def job_1505():
        publish_event("trigger_15h05", {"scheduled": True})

    scheduler.add_job(job_1500, CronTrigger(hour=15, minute=0), id="trigger_15h00")
    scheduler.add_job(job_1505, CronTrigger(hour=15, minute=5), id="trigger_15h05")
    scheduler.start()


@app.get("/orchestrator/status")
def orchestrator_status() -> dict:
    status = {}
    for name, info in processes.items():
        proc = info["process"]
        status[name] = {
            "running": proc.poll() is None,
            "returncode": proc.returncode,
            "command": info["command"],
            "uptime_seconds": int(time.time() - info["start_time"]),
        }
    return {"services": status, "last_events": last_events}


def boot_agents() -> None:
    for name, command in AGENTS.items():
        # command[1] already absolute from AGENTS; normalize for safety
        if command and command[0] == "python":
            command[1] = os.path.normpath(command[1])
        start_agent(name, command)


def startup() -> None:
    threading.Thread(target=monitor_agents, daemon=True).start()
    # Use APScheduler rather than busy-wait loops
    scheduler = BackgroundScheduler()
    schedule_with_apscheduler(scheduler)
    boot_agents()


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Orchestrator startup")
    startup()
