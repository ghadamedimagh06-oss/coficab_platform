#!/usr/bin/env python
"""
Quick verification script for CofICab Platform integration
"""

import socket
import time
import sys
from pathlib import Path

def check_port(host, port, service_name):
    """Check if a service is running on a specific port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ {service_name} is running on {host}:{port}")
            return True
        else:
            print(f"❌ {service_name} is NOT running on {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Error checking {service_name}: {e}")
        return False

def test_api_calls():
    """Test API connectivity"""
    try:
        import requests
    except ImportError:
        print("⚠️  requests library not found - skipping API tests")
        return False
    
    print("\n📡 Testing API endpoints:\n")
    
    base_url = "http://localhost:8001"
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
            status = "✅" if response.status_code == 200 else "⚠️"
            results.append(True)
            print(f"{status} {name}: {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: {str(e)[:50]}")
            results.append(False)
    
    return all(results)

def main():
    print("🔍 CofICab Platform - Integration Verification\n")
    print("=" * 60)
    
    services = [
        ("localhost", 5432, "PostgreSQL"),
        ("localhost", 8001, "FastAPI Backend"),
        ("localhost", 3001, "Next.js Frontend"),
    ]
    
    print("\n🔌 Checking Service Availability:\n")
    
    statuses = {}
    for host, port, name in services:
        statuses[name] = check_port(host, port, name)
    
    print("\n" + "=" * 60)
    
    # Test API if backend is running
    if statuses.get("FastAPI Backend"):
        if test_api_calls():
            print("\n✅ All API endpoints responding")
        else:
            print("\n⚠️  Some API endpoints are not responding")
    else:
        print("\n⚠️  Backend not running - cannot test API endpoints")
    
    print("\n" + "=" * 60)
    print("\n📋 Summary:\n")
    
    for service, running in statuses.items():
        status = "🟢 Running" if running else "🔴 Not Running"
        print(f"  {service}: {status}")
    
    print("\n" + "=" * 60)
    
    if all(statuses.values()):
        print("\n✅ All services running! Platform is operational.\n")
        return 0
    else:
        print("\n⚠️  Some services not running. Follow SYSTEM_FIX_GUIDE.md\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
