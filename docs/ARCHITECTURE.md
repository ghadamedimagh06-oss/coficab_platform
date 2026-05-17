# CofICab Platform - System Architecture

## Overview
The CofICab Platform is a distributed system designed for monitoring, tracking, and intelligent agent-based automation.

## Components

### 1. Frontend Dashboard (React + Next.js)
- User interface for visualization
- Real-time data display
- Task management UI
- Alert notifications

### 2. Backend API (FastAPI)
- RESTful API endpoints
- Database interactions
- Authentication & Authorization
- Business logic processing

### 3. Multi-Agent System (Python)

#### Agent 1: Watchdog
- File system monitoring
- Change detection
- Event logging

#### Agent 2: Scheduler
- Task scheduling
- Cron-like job management
- Execution monitoring

#### Agent 3: Alert Manager
- Alert creation and management
- Notification handling
- Severity classification

#### Agent 4: Tracker
- Data tracking and monitoring
- Item state management
- Historical data collection

### 4. Database (PostgreSQL)
- User management
- Agent configuration
- Event logging
- Task tracking
- Alert storage

## Communication Flow

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP/WebSocket
       ▼
┌─────────────────┐
│ Next.js Server  │
└──────┬──────────┘
       │ API Calls
       ▼
┌─────────────────┐
│   FastAPI       │
│   Backend       │
└──────┬──────────┘
       │ Query/Update
       ▼
┌─────────────────┐
│  PostgreSQL DB  │
└─────────────────┘

┌─────────────────────────────────┐
│   Python Agents                 │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌──┐  │
│ │ W/D │ │Sched│ │Alert│ │TK│  │
│ └─────┘ └─────┘ └─────┘ └──┘  │
└──────────┬──────────────────────┘
           │ Send Events/Data
           ▼
       FastAPI Backend
           (webhook endpoints)
```

## Data Flow

1. **Monitoring**: Agents collect data from system/files
2. **Processing**: FastAPI processes and stores data
3. **Storage**: Data persists in PostgreSQL
4. **Presentation**: Next.js dashboard displays information

## Deployment Architecture

- Frontend: Deployed on Vercel/Next.js hosting
- Backend: Docker container with Uvicorn
- Agents: Separate Python processes or containers
- Database: PostgreSQL server (local/cloud)
- Redis: Optional message queue for agent communication

---

For detailed setup and implementation, see README.md
