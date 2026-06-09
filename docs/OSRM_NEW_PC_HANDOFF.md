# OSRM Routing Handoff

This handoff explains how to run and work on the OSRM-backed planning version
from a fresh PC.

## What Changed

The generated daily planning flow now uses OSRM as the source of truth for road
distance, travel time, route legs, and route geometry.

Core files:

- `backend/app/services/osrm_service.py` - OSRM HTTP client and normalization.
- `backend/app/services/daily_plan_builder.py` - daily plan generation using OSRM matrices/routes.
- `backend/app/routes/optimization.py` - daily generate/export plus route recalculation endpoints.
- `backend/app/data/clients_directory.json` - 41 Tunisian client coordinates from the handoff data.
- `frontend/app/generated-daily-planning/page.jsx` - UI calls recalculation after edits.
- `frontend/components/planning/RouteSummary.jsx` - OSRM summary cards.
- `frontend/components/planning/RouteMap.jsx` - route geometry map.
- `frontend/components/planning/PlanTable.jsx` - route totals, leg km, travel/service display.
- `docs/OSRM_SETUP.md` - OSRM map setup details.

Main endpoints:

- `POST /api/planning/daily/generate`
- `POST /api/planning/daily/recalculate`
- `POST /api/planning/daily/export`
- `POST /api/optimization/route`

## Required Software

Install these on the new PC:

- Git
- Docker Desktop
- Python 3.10+
- Node.js 18+
- npm

Recommended checks:

```powershell
git --version
docker --version
python --version
node --version
npm --version
```

Start Docker Desktop before running OSRM.

## Repository Setup

Clone or copy the repo, then enter the project:

```powershell
cd "d:\pfe ghada\coficab_platform"
```

Install backend dependencies:

```powershell
cd backend
python -m pip install -r requirements.txt
cd ..
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

## OSRM Map Setup

The `osrm-data/` folder is ignored by Git because it contains large generated
map files. Each new PC must download and preprocess the map locally.

Create the folder:

```powershell
New-Item -ItemType Directory -Force -Path "osrm-data"
```

Download Tunisia from Geofabrik:

```powershell
Start-BitsTransfer `
  -Source "https://download.geofabrik.de/africa/tunisia-latest.osm.pbf" `
  -Destination "osrm-data\tunisia-latest.osm.pbf"
```

Expected file info used during this implementation:

```text
Size:   83,789,183 bytes
SHA256: 2BAE4C5357450859C759AEBE2010F5FAF7DE522D4DBA5CB442B00F3D570FD1C2
```

Optional verification:

```powershell
Get-Item "osrm-data\tunisia-latest.osm.pbf" | Select-Object Name,Length
Get-FileHash -Algorithm SHA256 "osrm-data\tunisia-latest.osm.pbf"
```

Preprocess for OSRM MLD routing:

```powershell
docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-extract -p /opt/car.lua /data/tunisia-latest.osm.pbf

docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-partition /data/tunisia-latest.osrm

docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-customize /data/tunisia-latest.osrm
```

After preprocessing, `osrm-data/` should contain `tunisia-latest.osrm` and many
sidecar files.

## Running The App Locally

Start OSRM:

```powershell
docker compose up -d osrm
```

Smoke test OSRM:

```powershell
Invoke-RestMethod "http://localhost:5000/nearest/v1/driving/10.2316,36.7703"
```

Expected: response contains `"code": "Ok"`.

Start backend locally:

```powershell
cd backend
$env:OSRM_BASE_URL = "http://localhost:5000"
$env:OSRM_PROFILE = "driving"
$env:WATCHER_ENABLED = "0"
$env:SCHEDULER_ENABLED = "0"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend health:

```powershell
Invoke-RestMethod "http://localhost:8000/api/health"
```

Start frontend:

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run build
npm run start
```

Open:

```text
http://localhost:3000/generated-daily-planning
```

## Docker Compose Notes

The compose files include an `osrm` service:

- `docker-compose.yml`
- `docker-compose-new.yml`
- root `docker-compose.no-db.yml`

When backend runs inside Docker Compose, use:

```text
OSRM_BASE_URL=http://osrm:5000
```

When backend runs directly on the host machine, use:

```text
OSRM_BASE_URL=http://localhost:5000
```

## How The Flow Works

Generation:

1. `DailyPlanBuilder` reads the workbook.
2. `GeoService` resolves clients using `clients_directory.json`.
3. `OSRMService.table()` calls `/table/v1/driving` for duration/distance matrices.
4. The planner groups stops by OSRM route insertion cost.
5. OR-Tools orders stops using OSRM durations.
6. For each final trip, `OSRMService.route()` calls `/route/v1/driving`.
7. Backend returns trip totals, legs, geometry, and stop ETAs.

Manual edits:

1. The frontend locally updates the dispatcher’s edited stop order.
2. It calls `POST /api/planning/daily/recalculate`.
3. Backend preserves stop order and recomputes OSRM route legs/geometry/timing.
4. Trips with missing coordinates are marked pending instead of breaking the plan.

## Quick API Tests

Generate a plan:

```powershell
$body = @{ day = "2026-05-26" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/planning/daily/generate" `
  -ContentType "application/json" `
  -Body $body
```

Test route endpoint:

```powershell
$body = @{
  deliveries = @(
    @{
      id = "aec"
      client = "AEC WIRING TECHNOLOGY SARL"
      lat = 36.72422
      lon = 10.18543
    }
  )
  trucks = @()
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/optimization/route" `
  -ContentType "application/json" `
  -Body $body
```

## Test Commands

Backend focused tests:

```powershell
python -m pytest --no-cov `
  backend\tests\test_daily_recalculate.py `
  backend\tests\test_osrm_service.py `
  backend\tests\test_planning_constraints.py `
  backend\tests\test_generated_daily_plan.py
```

Frontend build:

```powershell
cd frontend
npm run build
```

Expected current result:

```text
Backend focused tests: 11 passed
Frontend build: compiled successfully
```

The backend tests may print a Postgres authentication warning and run in offline
DB mode. That is expected for the workbook-based daily planner path.

## Important Implementation Rules

- Do not fall back silently to haversine for displayed route numbers.
- Use OSRM for final route distance, travel time, legs, and geometry.
- Treat Excel `ETD`/`ETA` as `requested_slot`, not a hard `time_window`.
- Hard time windows come from explicit constraints/comments.
- Default service time is `5 minutes * positions`.
- Manual stops need `lat/lon` to be recalculated by OSRM.
- If coordinates are missing, mark the trip pending with a clear route error.

## Current Known Limitation

Manual “Add delivery” can create free-text stops without coordinates. Those
cannot be routed until the UI provides coordinates, ideally by selecting from
the known client directory. The next recommended task is to replace the free
text client field with a searchable client selector that attaches `lat`, `lon`,
and `resolved_location`.

## Troubleshooting

Docker daemon not running:

```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

OSRM port check:

```powershell
Invoke-RestMethod "http://localhost:5000/nearest/v1/driving/10.2316,36.7703"
```

Backend cannot reach OSRM:

- Host backend: `OSRM_BASE_URL=http://localhost:5000`
- Compose backend: `OSRM_BASE_URL=http://osrm:5000`

Frontend cannot reach backend:

```powershell
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
```

Large generated files accidentally appear in Git:

```powershell
git status --short
```

`osrm-data/` should be ignored. Do not commit `.osm.pbf` or `.osrm*` files.
