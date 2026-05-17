#!/usr/bin/env python
"""
FINAL ACTION GUIDE - CofICab Integration Fix
Complete checklist with exact commands
"""

import sys

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def main():
    print("\n" + "="*70)
    print("  COFICAB PLATFORM - INTEGRATION FIX - FINAL STEPS")
    print("="*70)
    
    print_section("STEP 1: RESTART BACKEND (CRITICAL)")
    print("⚠️  The backend must be restarted to load code changes!\n")
    print("ACTION: In the terminal running uvicorn (8001):")
    print("  1. Press: Ctrl+C  (stop the server)")
    print("  2. Wait for: [Shutdown complete]")
    print("  3. Then run:")
    print("")
    print("  cd c:\\Users\\USER\\OneDrive\\Desktop\\coficab-platform\\backend")
    print("  uvicorn app.main:app --reload --port 8001")
    print("")
    print("✓ Expected output:")
    print("  INFO:     Uvicorn running on http://0.0.0.0:8001")
    print("  [OK] Database connection successful")
    print("  [OK] Database tables created successfully")
    
    print_section("STEP 2: VERIFY BACKEND RESTART")
    print("Give it 5 seconds, then check:")
    print("  - Backend terminal should show no errors")
    print("  - No 'Exception' messages in logs")
    
    print_section("STEP 3: TEST API CONNECTIVITY")
    print("Open browser and test each endpoint:\n")
    
    endpoints = [
        ("http://localhost:8001/api/health", "System Health"),
        ("http://localhost:8001/api/metrics/kpi", "KPI Metrics"),
        ("http://localhost:8001/api/tracking/live", "Live Tracking"),
        ("http://localhost:8001/api/data/transports", "Transport List"),
    ]
    
    for url, name in endpoints:
        print(f"  1. Visit: {url}")
        print(f"     Should return JSON data (not error)")
        print(f"  2. Then press F12 → Console")
        print(f"     Should show: [OK] API Response for {name}")
        print("")
    
    print_section("STEP 4: CHECK BROWSER CONSOLE FOR CORS")
    print("1. Open: http://localhost:3001/dashboard")
    print("2. Press: F12 (DevTools)")
    print("3. Click: Console tab")
    print("\n✓ Should see:")
    print("  [API Request] GET http://localhost:8001/api/metrics/kpi")
    print("  [API Response] 200 /api/metrics/kpi")
    print("\n✗ Should NOT see:")
    print("  Access to XMLHttpRequest blocked by CORS policy")
    print("  401 Unauthorized")
    print("  500 Internal Server Error")
    
    print_section("STEP 5: VERIFY DASHBOARD DATA")
    print("On dashboard page (http://localhost:3001/dashboard):\n")
    print("  [ ] KPI cards show real values (not 0):")
    print("      - Planning time: 85-145 seconds")
    print("      - Detection latency: 8-22 seconds")
    print("      - Error rate: 0.2%-0.8%")
    print("")
    print("  [ ] Performance chart displays bars")
    print("  [ ] Live fleet highlights show 2+ vehicles")
    print("  [ ] Chat panel shows welcome message")
    print("  [ ] All text is readable (not overlapping)")
    
    print_section("STEP 6: TEST OTHER PAGES")
    print("Click through navigation:\n")
    
    pages = [
        ("Map", "Truck markers with status colors"),
        ("Planning", "Route list with drag-drop interface"),
        ("Analytics", "Performance metrics and charts"),
        ("Admin", "File ingestion controls"),
    ]
    
    for page, expected in pages:
        print(f"  [ ] {page}: {expected}")
    
    print_section("STEP 7: DATABASE SETUP (OPTIONAL)")
    print("If you want real database data instead of mock:\n")
    print("1. Stop backend (Ctrl+C)")
    print("2. Run:")
    print("")
    print("   cd c:\\Users\\USER\\OneDrive\\Desktop\\coficab-platform")
    print("   python setup_database.py")
    print("")
    print("3. Then restart backend")
    print("4. Dashboard will show real database values")
    
    print_section("TROUBLESHOOTING")
    print("\nIf you see CORS errors:")
    print("  -> Backend didn't restart properly")
    print("  -> Stop it (Ctrl+C) and restart")
    print("  -> Hard refresh browser (Ctrl+Shift+R)")
    
    print("\nIf you see 500 errors on /api/data/transports:")
    print("  -> Backend code changes not loaded")
    print("  -> Restart backend with:")
    print("     uvicorn app.main:app --reload --port 8001")
    
    print("\nIf Dashboard shows 0 values:")
    print("  -> Normal if DB not set up")
    print("  -> Run setup_database.py to get real data")
    print("  -> Or just use mock data (current state)")
    
    print("\nIf API calls timeout:")
    print("  -> Backend not running on 8001")
    print("  -> Check if it's still on old port (8000?)")
    print("  -> Verify: netstat -ano | findstr :8001")
    
    print_section("QUICK TEST: ALL SYSTEMS GO?")
    print("\nRun this to verify everything:")
    print("")
    print("  python verify_system.py")
    print("")
    print("All [OK] = System ready")
    print("Any [FAIL] = See troubleshooting above")
    
    print_section("SUCCESS INDICATORS")
    print("\n✅ All systems working when you see:\n")
    print("  1. [OK] messages in verify_system.py output")
    print("  2. No CORS errors in browser console (F12)")
    print("  3. API calls logging with 200 status")
    print("  4. Dashboard shows KPI values > 0")
    print("  5. Map page loads with markers")
    print("  6. All navigation links work")
    
    print("\n" + "="*70)
    print("  READY? Start with STEP 1: Restart Backend!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
