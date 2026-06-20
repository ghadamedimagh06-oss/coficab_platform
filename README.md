# CofICab Platform

A multi-agent intelligent logistics platform that automates planning, monitors operations in real time, and reduces manual errors in transport management.

---

## Quick Start (Docker — recommended)

The whole stack — PostgreSQL, Redis, the backend API, the frontend, and all
four agents — comes up with one command. This is the supported path.

```bash
docker compose up -d
```

Then open:

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

Optional but recommended — warm the geocode cache offline before the first
plan is generated (otherwise the first build pays ~1s per uncached client):

```bash
docker compose exec backend python scripts/prewarm_geocode.py
```

Run the backend test suite:

```bash
docker compose exec backend pytest
```

---

## Development without Docker

Run the services manually in separate terminals (Windows PowerShell shown).

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 15+ | optional — backend runs without it |
| Redis | 7+ | optional — agents degrade gracefully |

### 1. Install dependencies

```powershell
cd backend; pip install -r requirements.txt
cd ..\frontend; npm install
```

### 2. Start everything (open 6 separate PowerShell terminals)

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

**Terminal 3 — Agent 1 (Collector)**
```powershell
cd "coficab_platform\agents\agent1_collector"
python main.py
```

**Terminal 4 — Agent 2 (Optimizer)**
```powershell
cd "coficab_platform\agents\agent2_optimizer"
python main.py
```

**Terminal 5 — Agent 3 (Notifier)**
```powershell
cd "coficab_platform\agents\agent3_notifier"
python main.py
```

**Terminal 6 — Agent 4 (Monitor)**
```powershell
cd "coficab_platform\agents\agent4_monitor"
python main.py
```

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
│   ├── agent1_collector/   # Watches shared_folder for new Excel files
│   ├── agent2_optimizer/   # Triggers route optimization runs
│   ├── agent3_notifier/    # KPI monitoring + Redis alerting
│   └── agent4_monitor/     # Transport polling + ETA calculation
├── database/               # PostgreSQL schema SQL
├── .env                    # Local environment config (do not commit)
└── docker-compose.yml      # Full stack via Docker (requires Docker Desktop)
```

---

## Multi-Agent Workflow

1. Drop an Excel planning file into `shared_folder/`
2. Agent 1 (Collector) detects it in < 1 second and triggers ingestion
3. Backend processes and stores data in PostgreSQL
4. Agent 2 (Optimizer) triggers route optimization
5. Agent 4 (Monitor) polls for transport updates every 5 minutes
6. Agent 3 (Notifier) monitors KPIs and fires alerts via Redis
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
| Copilot (LLM) | Groq Llama 3.3 70B (`llama-3.3-70b-versatile`) via any OpenAI-compatible endpoint |
| Auth | JWT (python-jose + passlib + bcrypt) |

---

## Dispatch Copilot (Optiroute)

The in-app assistant panel ("Optiroute") is a real LLM copilot. It talks to any
OpenAI-compatible chat endpoint — **Groq's free, fast Llama 3.3 70B by default** —
and streams answers grounded in (1) a snapshot of whatever screen the dispatcher
is on and (2) read-only tools that query the platform's own API (KPIs, fleet,
plan, incidents, tracking). So it can summarize a plan, flag risks, and explain
optimizer decisions over the whole platform, not just the current screen.

- Backend: `POST /api/copilot/chat` (streams the reply) and `GET /api/copilot/status`.
- Enable it by setting `GROQ_API_KEY` (or `COPILOT_API_KEY` / `OPENAI_API_KEY`)
  in the backend environment. Without a key the copilot input is disabled and the
  chat endpoint returns 503.
- Optional overrides: `COPILOT_MODEL` (default `llama-3.3-70b-versatile`),
  `COPILOT_BASE_URL` (default `https://api.groq.com/openai/v1`),
  `COPILOT_MAX_TOKENS` (default `1024`).
- Provider-agnostic: point `COPILOT_BASE_URL` + `COPILOT_MODEL` at Anthropic,
  OpenAI, Together, or a local Ollama and it works unchanged.

---

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Planning Time | 15–21 min | < 3 min |
| Detection Latency | ~4 hours | < 30 sec |

> Data quality depends on source workbook accuracy. The planner surfaces
> mismatches (e.g. split-quantity warnings) explicitly in the API response
> rather than silently correcting them.

---

## Known Limitations

- **Travel times** are haversine-based with a fixed ~55 km/h estimate and a
  road-winding factor. Real road-network routing via OSRM is planned but not
  yet implemented.
- **Driver HOS** (hours-of-service) violations are flagged as warnings only,
  in `diagnostics.hos_warnings`, and shown as a ⚠ badge on the Gantt. Legal
  compliance with Tunisian driving regulations remains the dispatcher's
  responsibility.
- **Delivery splits** are driven by free-text workbook comments
  (e.g. `"24pos beja1 8pos beja 2"`). The planner validates totals and surfaces
  quantity mismatches, but does not prevent typos at the source.
- **Planning latency** (~12s on the generate endpoint) is dominated by the
  OR-Tools combinatorial optimization, not geocoding. The geocode cache is
  pre-warmed offline via `scripts/prewarm_geocode.py`.
