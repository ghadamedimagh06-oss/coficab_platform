"""
FastAPI Main Application
CofICab Platform Backend
"""

from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import datetime

from app.routes import (
    metrics,
    tracking,
    ingestion,
    optimization,
    data,
    auth,
    tasks,
    planning_governance,
    delivery_split,
    agents,
    fleet,
    incidents,
    dispatch,
)
from app.database import engine, Base
from app.agents.scheduler import start_scheduler
from app.services.excel_watcher import ExcelWatcherService
import app.models

_default_watch = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "weekly planning")
_default_archive = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "archive")
WATCH_PATH = os.getenv("WATCH_PATH", _default_watch)
ARCHIVE_PATH = os.getenv("ARCHIVE_PATH", _default_archive)
WATCHER_ENABLED = os.getenv("WATCHER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

# Create database tables if database is available
if engine:
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
    except Exception as e:
        print(f"Failed to create database tables: {e}")
        print("Running without database - some endpoints will fail")
else:
    print("Database not available - running in offline mode")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.watcher_service = None
    app.state.scheduler = None

    if WATCHER_ENABLED:
        print(f"[WATCHDOG] WATCHER_ENABLED=true, starting watcher for {WATCH_PATH}")
        watcher = ExcelWatcherService(WATCH_PATH, ARCHIVE_PATH)
        app.state.watcher_service = watcher
        watcher.start()
    else:
        print("[WATCHDOG] WATCHER_ENABLED=false, watcher will not start")

    if SCHEDULER_ENABLED:
        print("[SCHEDULER] SCHEDULER_ENABLED=true, starting backend jobs")
        app.state.scheduler = start_scheduler()
    else:
        print("[SCHEDULER] SCHEDULER_ENABLED=false, backend jobs will not start")

    try:
        yield
    finally:
        watcher_service = getattr(app.state, "watcher_service", None)
        if watcher_service is not None:
            watcher_service.stop()
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="CofICab Platform API",
    description="Backend API for CofICab Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware - Allow both frontend dev ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(tracking.router, prefix="/api/tracking", tags=["tracking"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["ingestion"])
app.include_router(optimization.router, prefix="/api/optimization", tags=["optimization"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(planning_governance.router, prefix="/api/planning", tags=["planning"])
app.include_router(optimization.daily_router, prefix="/api/planning", tags=["daily-planning"])
app.include_router(delivery_split.router, prefix="/api", tags=["delivery-split"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(fleet.router, prefix="/api/fleet", tags=["fleet"])
app.include_router(fleet.clients_router, prefix="/api/clients", tags=["clients"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(dispatch.router, prefix="/api/dispatch", tags=["dispatch"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CofICab Platform API",
        "status": "active",
        "timestamp": datetime.datetime.now().isoformat()
    }


@app.get("/api/health")
async def health_check():
    """System health check"""
    db_status = "connected" if engine else "disconnected"
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
