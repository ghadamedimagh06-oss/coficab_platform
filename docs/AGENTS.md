# Multi-Agent System Specification

## Overview
The CofICab Platform uses 4 specialized agents working in coordination to automate logistics operations.

## Agent 1: Watchdog (Ingestion Trigger)

**Purpose**: Real-time file monitoring and ingestion pipeline trigger

**Responsibilities**:
- Monitor shared folder for new Excel files
- Detect new planning files (< 1 second response)
- Trigger ingestion pipeline via API

**Technology**:
- `watchdog` library for file system events
- HTTP requests to backend API

**Configuration**:
- `WATCH_DIRECTORY`: Path to monitor (default: `./shared_folder`)
- `BACKEND_API_URL`: Backend API endpoint (default: `http://localhost:8000`)

**Sample Output**:
```
[WATCHDOG] Excel file detected: /shared_folder/plan_2026_05.xlsx
[WATCHDOG] Ingestion pipeline triggered successfully
```

---

## Agent 2: Scheduler (Automation Engine)

**Purpose**: Execute time-based scheduled tasks

**Responsibilities**:
- Execute daily planning tasks
- Process data at regular intervals
- Perform system health checks

**Technology**:
- `APScheduler` for job scheduling
- Background task execution

**Scheduled Jobs**:
1. **Daily Planning** - Runs at 00:00 daily
2. **Data Processing** - Runs every 1 hour
3. **Health Check** - Runs every 5 minutes

**Configuration**:
- `BACKEND_API_URL`: Backend API endpoint

**Sample Output**:
```
[SCHEDULER] Started with 3 scheduled jobs
[SCHEDULER] Daily planning task executed
[SCHEDULER] Daily planning completed: 200
```

---

## Agent 3: Alert Monitor (Decision Layer)

**Purpose**: Monitor KPIs and detect system anomalies

**Responsibilities**:
- Monitor planning time KPI
- Monitor detection latency
- Monitor data error rate
- Generate alerts when thresholds exceeded

**KPI Thresholds**:
- Planning Time: 180 seconds
- Detection Latency: 30 seconds
- Data Error Rate: 1%

**Technology**:
- Redis for fast alert storage
- HTTP requests to backend API

**Alert Severity Levels**:
- `info` - Informational
- `warning` - Warning level
- `critical` - Critical issue

**Configuration**:
- `BACKEND_API_URL`: Backend API endpoint
- `REDIS_URL`: Redis connection (default: `redis://localhost:6379`)
- `MONITOR_INTERVAL`: Check frequency in seconds (default: 10)

**Sample Output**:
```
[ALERT] Alert created: planning_time [warning] - Planning time exceeded: 250s > 180s
[ALERT] Alert created: detection_latency [critical] - Detection latency high: 45s > 30s
```

---

## Agent 4: TFM Tracker (Real-Time Tracking)

**Purpose**: Track transport status in real-time

**Responsibilities**:
- Poll TFM system every 5 minutes
- Calculate ETA based on distance and speed
- Update real-time tracking data
- Sync data to backend

**Technology**:
- HTTP polling to TFM API
- ETA calculation algorithms
- Real-time data sync

**Poll Interval**: 5 minutes (300 seconds)

**Tracking Data Includes**:
- Transport ID
- Current status
- Location coordinates
- ETA hours
- Distance remaining
- Update timestamp

**Configuration**:
- `BACKEND_API_URL`: Backend API endpoint
- `TFM_API_URL`: TFM system endpoint (default: `http://tfm-api:8080`)
- `POLL_INTERVAL`: Poll frequency in seconds (default: 300)

**Sample Output**:
```
[TRACKER] Polling TFM system at 2026-05-04T10:30:00
[TRACKER] Updated transport transport_001: ETA 2.5h
[TRACKER] Synced 25 transports
```

---

## Agent Coordination

### Data Flow:
```
Watchdog (Excel detected)
    ↓
Agent 1 triggers ingestion
    ↓
Backend processes data
    ↓
Scheduler orchestrates tasks
    ↓
Tracker updates real-time status
    ↓
Alert Monitor checks KPIs
    ↓
Dashboard displays live data
```

### Communication:
- All agents communicate through **HTTP REST API** with backend
- Alert storage uses **Redis** for fast access
- Data persistence uses **PostgreSQL** database

---

## Environment Variables

Required environment variables for all agents:

```bash
# Backend API
BACKEND_API_URL=http://localhost:8000

# Agent 1: Watchdog
WATCH_DIRECTORY=./shared_folder

# Agent 3: Alert Monitor
REDIS_URL=redis://localhost:6379
MONITOR_INTERVAL=10

# Agent 4: TFM Tracker
TFM_API_URL=http://tfm-api:8080
POLL_INTERVAL=300
```

---

## Deployment

### Docker Compose Example:
```yaml
version: '3.8'

services:
  agent1_watchdog:
    build: ./agents/agent1_watchdog
    environment:
      - WATCH_DIRECTORY=/shared_folder
      - BACKEND_API_URL=http://backend:8000
    volumes:
      - ./shared_folder:/shared_folder

  agent2_scheduler:
    build: ./agents/agent2_scheduler
    environment:
      - BACKEND_API_URL=http://backend:8000

  agent3_alert:
    build: ./agents/agent3_alert
    environment:
      - BACKEND_API_URL=http://backend:8000
      - REDIS_URL=redis://redis:6379
      - MONITOR_INTERVAL=10

  agent4_tracker:
    build: ./agents/agent4_tracker
    environment:
      - BACKEND_API_URL=http://backend:8000
      - TFM_API_URL=http://tfm-api:8080
      - POLL_INTERVAL=300
```
