"""
Agent 3 - Alert Monitor (Decision Layer)

Monitors KPIs and thresholds.
Detects anomalies (delays, inconsistencies).
Uses Redis for fast alert handling.

Role: Intelligence & alert system
"""

import os
import time
import logging
import requests
import redis
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "10"))  # seconds

# KPI Thresholds
THRESHOLD_PLANNING_TIME = 180  # seconds
THRESHOLD_DETECTION_LATENCY = 30  # seconds
THRESHOLD_DATA_ERROR_RATE = 0.01  # 1%


class AlertManager:
    """Manages KPI monitoring and alert generation."""

    def __init__(self):
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            self.redis_client.ping()
            logger.info("[ALERT] Redis connection established")
        except Exception as e:
            logger.warning(f"[ALERT] Redis unavailable: {e}")
            self.redis_client = None

    def check_kpi_planning_time(self, actual_time):
        """Check if planning time exceeds threshold."""
        if actual_time > THRESHOLD_PLANNING_TIME:
            return self.create_alert(
                "planning_time",
                f"Planning time exceeded: {actual_time}s > {THRESHOLD_PLANNING_TIME}s",
                "warning"
            )
        return None

    def check_kpi_detection_latency(self, latency):
        """Check if detection latency exceeds threshold."""
        if latency > THRESHOLD_DETECTION_LATENCY:
            return self.create_alert(
                "detection_latency",
                f"Detection latency high: {latency}s > {THRESHOLD_DETECTION_LATENCY}s",
                "critical"
            )
        return None

    def check_kpi_data_errors(self, error_rate):
        """Check if data error rate exceeds threshold."""
        if error_rate > THRESHOLD_DATA_ERROR_RATE:
            return self.create_alert(
                "data_errors",
                f"High error rate: {error_rate*100:.2f}% > {THRESHOLD_DATA_ERROR_RATE*100:.2f}%",
                "critical"
            )
        return None

    def create_alert(self, alert_type, message, severity="info"):
        """Create and store a new alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"[ALERT] Alert created: {alert_type} [{severity}] - {message}")
        
        if self.redis_client:
            try:
                self.redis_client.lpush(f"alerts:{alert_type}", str(alert))
            except Exception as e:
                logger.error(f"[ALERT] Failed to store alert in Redis: {e}")
        
        return alert

    def fetch_and_monitor_metrics(self):
        """Fetch metrics from backend and monitor KPIs."""
        try:
            response = requests.get(
                f"{BACKEND_API_URL}/api/metrics/kpi",
                timeout=5
            )
            if response.status_code == 200:
                metrics = response.json()
                logger.info(f"[ALERT] Metrics fetched: {metrics}")
                
                # Check KPIs
                if "planning_time" in metrics:
                    self.check_kpi_planning_time(metrics["planning_time"])
                if "detection_latency" in metrics:
                    self.check_kpi_detection_latency(metrics["detection_latency"])
                if "data_error_rate" in metrics:
                    self.check_kpi_data_errors(metrics["data_error_rate"])
        except Exception as e:
            logger.error(f"[ALERT] Failed to fetch metrics: {e}")


def start_alert_monitor():
    """Start continuous KPI monitoring."""
    manager = AlertManager()
    logger.info("[ALERT] Monitor started")
    
    try:
        while True:
            manager.fetch_and_monitor_metrics()
            time.sleep(MONITOR_INTERVAL)
    except KeyboardInterrupt:
        logger.info("[ALERT] Monitor stopped")


if __name__ == "__main__":
    start_alert_monitor()
