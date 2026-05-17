# CofICab Platform

A multi-agent intelligent logistics platform designed to automate planning, monitor operations in real time, and reduce manual errors in transport management.

## 🎯 Project Objective

The goal of this platform is to transform a manual, reactive logistics process into a:

- ⚡ Real-time monitored system
- 🤖 Automated decision pipeline
- 📊 Data-driven control dashboard

## 🧠 Problem Statement

The current system suffers from:

- ⏱️ Heavy manual planning (15–21 min per plan)
- 🐌 Delayed issue detection (~4 hours latency)
- ⚠️ High data error rate (12–18%)

## 🚀 Proposed Solution

A multi-agent system integrated with a 5-layer architecture, enabling:

- Real-time data ingestion
- Automated scheduling
- Intelligent alerting
- Continuous tracking (ETA, delays)

## 🏗️ System Architecture

```
coficab-platform/
│
├── frontend/        # React + Next.js Dashboard
├── backend/         # FastAPI Application
├── agents/          # Multi-Agent System
│   ├── agent1_watchdog/      # File/System monitoring
│   ├── agent2_scheduler/     # Task scheduling
│   ├── agent3_alert/         # Alert management
│   └── agent4_tracker/       # Data tracking
├── database/        # PostgreSQL schema
├── docs/            # PFE documentation
└── README.md
```

## 🤖 Multi-Agent System (Core of the Platform)

The system is driven by 4 specialized agents, each responsible for a critical part of the pipeline.

### 🟢 Agent 1 — Watchdog (Ingestion Trigger)

- Monitors shared folder in real time
- Detects new Excel planning files (< 1 second)
- Triggers ingestion pipeline

**Role**: Entry point of the system

### 🔵 Agent 2 — Scheduler (Automation Engine)

- Executes scheduled tasks (daily planning, processing)
- Manages time-based workflows using APScheduler

**Role**: System orchestrator

### 🟠 Agent 3 — Alert Monitor (Decision Layer)

- Monitors KPIs and thresholds
- Detects anomalies (delays, inconsistencies)
- Uses Redis for fast alert handling

**Role**: Intelligence & alert system

### 🟣 Agent 4 — TFM Tracker (Real-Time Tracking)

- Polls TFM system every 5 minutes
- Calculates ETA and transport status
- Updates real-time data

**Role**: Live tracking & visibility

## 🧱 Platform Layers

The system follows a 5-layer architecture:

- 🟩 **Layer 1 — Ingestion**: File detection (watchdog), Data processing (pandas), Scheduling triggers
- 🟦 **Layer 2 — Optimization & AI**: Route optimization (OR-Tools), Data matching (rapidfuzz)
- 🟪 **Layer 3 — Storage**: PostgreSQL (structured data), Redis (real-time processing)
- 🟥 **Layer 4 — Backend API**: FastAPI, Business logic, Authentication (JWT)
- 🟨 **Layer 5 — Interfaces**: React dashboard, KPI visualization, Driver mobile interface

## 📊 Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Planning Time | 15–21 min | < 3 min |
| Detection Latency | ~4 hours | < 30 sec |
| Data Errors | 12–18% | ~0% |

## ⚙️ Technology Stack

### Frontend
- React (Next.js)
- TypeScript
- Tailwind CSS

### Backend
- Python
- FastAPI
- SQLAlchemy

### Multi-Agent System
- Python
- watchdog
- APScheduler
- Redis

### Database
- PostgreSQL

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.9+
- PostgreSQL
- Redis

### Setup Instructions

#### 1. Frontend
```bash
cd frontend
npx create-next-app@latest .
npm install
npm run dev
```

#### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary
uvicorn app.main:app --reload
```

#### 3. Agents
```bash
cd agents
pip install watchdog apscheduler redis pandas
```

#### 4. Database
```bash
psql -U postgres -d coficab_db -f database/schema.sql
```

## 🔄 System Workflow (VERY IMPORTANT FOR JURY)

1. Excel file is uploaded to shared folder
2. Agent 1 detects it instantly
3. Data is processed and stored
4. Agent 2 schedules tasks
5. Agent 4 updates real-time tracking
6. Agent 3 monitors KPIs and triggers alerts
7. Dashboard displays live data

## 🧪 Development Strategy

Components are decoupled:

- **Frontend** → UI & visualization
- **Backend** → API & logic
- **Agents** → automation & intelligence

Each can run independently.

## 📁 Documentation

See `/docs` for:

- Architecture diagrams
- PFE chapters
- Requirements
- Agent specifications

## 🎯 Project Status

🚧 In Development (Agile Sprint Execution)

---

**Project**: CofICab Platform
**Status**: In Development
"# coficab_platform" 
