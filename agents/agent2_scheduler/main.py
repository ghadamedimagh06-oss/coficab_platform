"""
Agent 2 - Scheduler (Automation Engine)

Executes scheduled tasks with VRP optimization.
Runs nightly to generate optimized delivery routes.

Role: System orchestrator + VRP trigger
"""

import os
import logging
import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")


# ============================================================
# 1. VRP OPTIMIZATION — el task el muhimma
# ============================================================

def vrp_optimization_task():
    """
    Kol lila — yakhoudh planning nhar ghudwa
    w ycharli VRP algorithm lil routes.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%A")  # ex: "Tuesday"
    logger.info(f"[SCHEDULER] Starting VRP optimization for {tomorrow}...")

    try:
        # Step 1: jib deliveries nhar ghudwa mel backend
        deliveries_resp = requests.get(
            f"{BACKEND_API_URL}/api/data/transports",
            params={"day": tomorrow},
            timeout=10
        )

        if deliveries_resp.status_code != 200:
            logger.error(f"[SCHEDULER] Could not fetch deliveries: {deliveries_resp.status_code}")
            return

        deliveries = deliveries_resp.json().get("transports", [])
        logger.info(f"[SCHEDULER] Found {len(deliveries)} deliveries for {tomorrow}")

        if not deliveries:
            logger.info(f"[SCHEDULER] No deliveries for {tomorrow} — skipping VRP")
            return

        # Step 2: jib camions disponibles
        trucks_resp = requests.get(
            f"{BACKEND_API_URL}/api/data/trucks",
            params={"available": True},
            timeout=10
        )
        trucks = trucks_resp.json().get("trucks", []) if trucks_resp.status_code == 200 else []
        logger.info(f"[SCHEDULER] Available trucks: {len(trucks)}")

        # Step 3: charli VRP endpoint
        vrp_payload = {
            "day": tomorrow,
            "deliveries": deliveries,
            "trucks": trucks,
            "source": "SCHEDULER_AUTO",          # moch human
            "optimize_for": "distance",          # wla "time" wla "balanced"
            "max_stops_per_truck": 15,
            "depot_location": "Tunis"
        }

        vrp_resp = requests.post(
            f"{BACKEND_API_URL}/api/optimization/vrp",
            json=vrp_payload,
            timeout=60  # VRP ye5oudh wa9t
        )

        if vrp_resp.status_code == 200:
            result = vrp_resp.json()
            logger.info(f"[SCHEDULER] ✅ VRP done:")
            logger.info(f"  → Routes generated: {result.get('routes_count', 0)}")
            logger.info(f"  → Total distance: {result.get('total_distance_km', 0)} km")
            logger.info(f"  → Estimated savings: {result.get('savings_percent', 0)}%")
        else:
            logger.error(f"[SCHEDULER] ❌ VRP failed: {vrp_resp.status_code} — {vrp_resp.text}")

    except Exception as e:
        logger.error(f"[SCHEDULER] ❌ VRP error: {e}")


# ============================================================
# 2. DAILY PLANNING — yvalidi planning nhar jdid
# ============================================================

def daily_planning_task():
    """
    Essbe7 — ychargi planning nhar el yawm
    w ymarki routes ka IN_EXECUTION.
    """
    today = datetime.now().strftime("%A")
    logger.info(f"[SCHEDULER] Activating planning for {today}...")

    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/tasks/daily-planning",
            json={"day": today, "source": "SCHEDULER_AUTO"},
            timeout=30
        )
        if response.status_code == 200:
            logger.info(f"[SCHEDULER] ✅ Planning activated for {today}")
        else:
            logger.error(f"[SCHEDULER] ❌ Failed: {response.status_code}")
    except Exception as e:
        logger.error(f"[SCHEDULER] ❌ Error: {e}")


# ============================================================
# 3. HEALTH CHECK
# ============================================================

def health_check_task():
    """Kol 5 dqa9iq — yverifi el backend chaghal."""
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/health", timeout=5)
        if response.status_code == 200:
            db = response.json().get("database", "unknown")
            logger.info(f"[SCHEDULER] ✅ Health OK — DB: {db}")
        else:
            logger.warning(f"[SCHEDULER] ⚠ Health check: {response.status_code}")
    except Exception as e:
        logger.error(f"[SCHEDULER] ❌ Backend unreachable: {e}")


# ============================================================
# 4. PENDING REVIEW REMINDER
# ============================================================

def pending_review_reminder():
    """
    Kol sa3a — yshuf itha fama planning
    mazal PENDING_REVIEW bla ma ye3mel 7aja.
    """
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/planning/pending",
            timeout=10
        )
        if response.status_code == 200:
            pending = response.json().get("pending_count", 0)
            if pending > 0:
                logger.warning(
                    f"[SCHEDULER] ⚠ {pending} planning(s) PENDING_REVIEW "
                    f"— responsable lezem yreview!"
                )
    except Exception as e:
        logger.error(f"[SCHEDULER] ❌ Pending check error: {e}")


# ============================================================
# START
# ============================================================

def start_scheduler():
    """Start APScheduler with all jobs."""
    scheduler = BackgroundScheduler()

    # 🧠 VRP — kol lila 23:00 (9bal midnight)
    scheduler.add_job(
        vrp_optimization_task,
        'cron', hour=23, minute=0,
        id='vrp_optimization',
        name='VRP nightly optimization'
    )

    # 📅 Daily planning — kol ssbe7 6:00
    scheduler.add_job(
        daily_planning_task,
        'cron', hour=6, minute=0,
        id='daily_planning',
        name='Daily planning activation'
    )

    # ⚠ Pending review reminder — kol sa3a
    scheduler.add_job(
        pending_review_reminder,
        'interval', hours=1,
        id='pending_review',
        name='Pending review reminder'
    )

    # 💓 Health check — kol 5 dqa9iq
    scheduler.add_job(
        health_check_task,
        'interval', minutes=5,
        id='health_check',
        name='Health check'
    )

    scheduler.start()
    logger.info("[SCHEDULER] ✅ Started with 4 jobs:")
    logger.info("  → 23:00 — VRP optimization")
    logger.info("  → 06:00 — Daily planning activation")
    logger.info("  → /1h   — Pending review reminder")
    logger.info("  → /5min — Health check")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("[SCHEDULER] Stopped")


if __name__ == "__main__":
    start_scheduler()
