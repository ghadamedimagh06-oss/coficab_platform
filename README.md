# CofICab Platform

A multi-agent intelligent logistics platform that automates planning, monitors operations in real time, and reduces manual errors in transport management.

---

## Quick Start (Windows PowerShell)

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 15+ | optional — backend runs without it |
| Redis | 7+ | optional — agents degrade gracefully |

### 1. Install Python dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 2. Install frontend dependencies

```powershell
cd frontend
npm install
```

### 3. Start everything (open 6 separate PowerShell terminals)

**Terminal 1 — Backend API**
```powershell
cd "coficab_platform\backend"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend**
```powershell
cd "coficab_platform\frontend"
npm run dev
```

**Terminal 3 — Agent 1 (Watchdog)**
```powershell
cd "coficab_platform\agents\agent1_watchdog"
python main.py
```

**Terminal 4 — Agent 2 (Scheduler)**
```powershell
cd "coficab_platform\agents\agent2_scheduler"
python main.py
```

**Terminal 5 — Agent 3 (Alert Monitor)**
```powershell
cd "coficab_platform\agents\agent3_alert"
python main.py
```

**Terminal 6 — Agent 4 (TFM Tracker)**
```powershell
cd "coficab_platform\agents\agent4_tracker"
python main.py
```

### Access

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## Environment Variables

A `.env` file is already configured at the project root. Copy it to the backend folder if needed:

```powershell
copy .env backend\.env
```

Key variables:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/coficab_db
NEXT_PUBLIC_API_URL=http://localhost:8000
JWT_SECRET=change_this_secret_in_production
```

---

## Database Setup (PostgreSQL)

If PostgreSQL is installed and running:

```powershell
psql -U postgres -c "CREATE DATABASE coficab_db;"
psql -U postgres -d coficab_db -f database\schema.sql
```

The backend creates tables automatically on startup via SQLAlchemy. Without a database it runs in offline mode — most endpoints still respond with mock data.

---

## Dependency Notes

- `uvicorn` must be run as `python -m uvicorn` (not `uvicorn` directly) on Windows unless the Python Scripts folder is in PATH
- `ortools` is required for route optimization. If missing: `pip install ortools==9.15.6755`
- `redis` is optional. Agent 3 logs a warning but continues without it
- Frontend uses Next.js 13. Do not upgrade to 14+ without reviewing breaking changes in the app/ directory

---

## System Architecture

```
coficab_platform/
├── frontend/               # Next.js 13 + Tailwind CSS dashboard
├── backend/                # FastAPI + SQLAlchemy REST API
│   ├── app/
│   │   ├── main.py         # App entry point, lifespan, CORS
│   │   ├── database.py     # SQLAlchemy engine + session
│   │   ├── models/         # ORM models
│   │   ├── routes/         # API routers (metrics, tracking, auth, ...)
│   │   └── services/       # Business logic, Excel watcher, VRPTW
│   └── requirements.txt
├── agents/
│   ├── agent1_watchdog/    # Watches shared_folder for new Excel files
│   ├── agent2_scheduler/   # APScheduler-based task runner
│   ├── agent3_alert/       # KPI monitoring + Redis alerting
│   └── agent4_tracker/     # TFM polling + ETA calculation
├── database/               # PostgreSQL schema SQL
├── .env                    # Local environment config (do not commit)
└── docker-compose.yml      # Full stack via Docker (requires Docker Desktop)
```

---

## Docker (alternative)

If Docker Desktop is installed, this starts everything in one command:

```powershell
cd coficab_platform
docker-compose up --build
```

---

## Multi-Agent Workflow

1. Drop an Excel planning file into `shared_folder/`
2. Agent 1 detects it in < 1 second and triggers ingestion
3. Backend processes and stores data in PostgreSQL
4. Agent 2 schedules downstream tasks
5. Agent 4 polls for transport updates every 5 minutes
6. Agent 3 monitors KPIs and fires alerts via Redis
7. Dashboard at `localhost:3000` displays live data

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 13, React 18, TypeScript, Tailwind CSS |
| Backend | Python 3.10, FastAPI, SQLAlchemy, Pydantic v2 |
| Agents | watchdog, APScheduler, redis-py, pandas |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Optimization | OR-Tools 9.15 |
| Auth | JWT (python-jose + passlib + bcrypt) |

---

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Planning Time | 15–21 min | < 3 min |
| Detection Latency | ~4 hours | < 30 sec |
| Data Error Rate | 12–18% | ~0% |
