from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.daily_plan_builder import DailyPlanBuilder
from app.services.excel_exporter import export_plan_to_xlsx
from app.services.vrptw_optimizer import VRPTWOptimizer


router = APIRouter()
daily_router = APIRouter(prefix="/daily")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEEKLY_DIR = PROJECT_ROOT / "weekly planning"
EXPORT_DIR = WEEKLY_DIR / "exports"


class PlanningGenerateRequest(BaseModel):
    deliveries: List[Dict[str, Any]]
    trucks: List[Dict[str, Any]] = []
    current_routes: List[Dict[str, Any]] = []


class RouteOptimization(BaseModel):
    deliveries: List[Dict[str, Any]] = []
    trucks: List[Dict[str, Any]] = []


class DailyGenerateRequest(BaseModel):
    day: str
    source_file: Optional[str] = None


class DailyExportRequest(BaseModel):
    source_file: str
    day: str
    plan: Dict[str, Any]


@router.post("/route")
async def optimize_route(request: RouteOptimization):
    return {
        "status": "optimized",
        "original_distance": 1000,
        "optimized_distance": 850,
        "savings_percent": 15,
        "deliveries": len(request.deliveries),
        "trucks": len(request.trucks),
    }


@router.post("/planning/generate")
async def generate_planning(request: PlanningGenerateRequest):
    try:
        optimizer = VRPTWOptimizer(request.deliveries, request.trucks, request.current_routes)
        result = optimizer.optimize()
        return {
            "status": result["status"],
            "algorithm": result["algorithm"],
            "routes": result["routes"],
            "unassigned": result["unassigned"],
            "costs": result["costs"],
            "suggestions": result["suggestions"],
            "metrics": result["metrics"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}") from exc


@daily_router.post("/generate")
async def generate_daily_plan(request: DailyGenerateRequest):
    try:
        builder = DailyPlanBuilder(WEEKLY_DIR)
        return builder.build(day=_parse_day(request.day), source_file=request.source_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.post("/export")
async def export_daily_plan(request: DailyExportRequest):
    try:
        source_path = (WEEKLY_DIR / request.source_file).resolve()
        if WEEKLY_DIR.resolve() not in source_path.parents:
            raise ValueError("source_file must stay inside weekly planning")
        out_path = export_plan_to_xlsx(source_path, request.plan, EXPORT_DIR)
        return {
            "download_url": f"/api/planning/daily/download/{out_path.name}",
            "file_name": out_path.name,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.get("/download/{file_name}")
async def download_daily_plan(file_name: str):
    path = (EXPORT_DIR / file_name).resolve()
    if EXPORT_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="export not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


def _parse_day(raw: str):
    from datetime import date

    return date.fromisoformat(raw)
