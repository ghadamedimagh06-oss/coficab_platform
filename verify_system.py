#!/usr/bin/env python
"""
Quick verification script for CofICab Platform integration.
"""

import os
import socket
import sys
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def http_target(name, default_port):
    url_value = os.getenv(f"{name}_URL")
    if url_value:
        parsed = urlparse(url_value)
        scheme = parsed.scheme or "http"
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if scheme == "https" else 80)
        return f"{scheme}://{host}:{port}", host, port

    host = os.getenv(f"{name}_HOST", "localhost")
    port = int(os.getenv(f"{name}_PORT", str(default_port)))
    return f"http://{host}:{port}", host, port


def tcp_target(name, default_host, default_port):
    host = os.getenv(f"{name}_HOST", default_host)
    port = int(os.getenv(f"{name}_PORT", str(default_port)))
    return host, port


def check_port(host, port, service_name):
    """Check if a service is running on a specific port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"[OK] {service_name} is running on {host}:{port}")
            return True

        print(f"[FAIL] {service_name} is NOT running on {host}:{port}")
        return False
    except Exception as exc:
        print(f"[FAIL] Error checking {service_name}: {exc}")
        return False


def test_api_calls(base_url):
    """Test API connectivity and database health."""
    try:
        import requests
    except ImportError:
        print("[WARN] requests library not found - skipping API tests")
        return False

    print("\nTesting API endpoints:\n")

    endpoints = [
        ("/api/health", "Health Check"),
        ("/api/metrics/kpi", "KPI Metrics"),
        ("/api/tracking/live", "Live Tracking"),
        ("/api/data/transports", "Transport List"),
    ]

    results = []
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=3)
            endpoint_ok = response.status_code == 200

            if endpoint == "/api/health" and endpoint_ok:
                data = response.json()
                db_details = data.get("database_details") or {}
                db_ok = db_details.get("ok", data.get("database") == "connected")
                if not db_ok:
                    endpoint_ok = False
                    reason = db_details.get("error") or db_details.get("missing_tables")
                    print(f"Database Connection: {data.get('database')} - {reason}")

            status = "[OK]" if endpoint_ok else "[WARN]"
            print(f"{status} {name}: {response.status_code}")
            results.append(endpoint_ok)
        except Exception as exc:
            print(f"[FAIL] {name}: {str(exc)[:80]}")
            results.append(False)

    return all(results)


def main():
    print("CofICab Platform - Integration Verification\n")
    print("=" * 60)

    backend_url, backend_host, backend_port = http_target("BACKEND", 8000)
    _, frontend_host, frontend_port = http_target("FRONTEND", 3000)
    postgres_host, postgres_port = tcp_target("POSTGRES", "localhost", 5432)

    services = [
        (postgres_host, postgres_port, "PostgreSQL"),
        (backend_host, backend_port, "FastAPI Backend"),
        (frontend_host, frontend_port, "Next.js Frontend"),
    ]

    print("\nChecking Service Availability:\n")

    statuses = {}
    for host, port, name in services:
        statuses[name] = check_port(host, port, name)

    print("\n" + "=" * 60)

    api_ok = False
    if statuses.get("FastAPI Backend"):
        api_ok = test_api_calls(backend_url)
        if api_ok:
            print("\n[OK] All API endpoints and database checks passed")
        else:
            print("\n[WARN] API checks did not fully pass")
    else:
        print("\n[WARN] Backend not running - cannot test API endpoints")

    print("\n" + "=" * 60)
    print("\nSummary:\n")

    for service, running in statuses.items():
        status = "Running" if running else "Not running"
        print(f"  {service}: {status}")

    print("\n" + "=" * 60)

    if all(statuses.values()) and api_ok:
        print("\n[OK] All services running. Platform is operational.\n")
        return 0

    print("\n[WARN] Verification failed. Check service logs and database credentials.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
