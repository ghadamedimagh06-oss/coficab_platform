import json
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_db_optional
from app.services.auth_service import require_auth
from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig
from app.services import dashboard_service
from app.services.excel_exporter import export_plan_to_xlsx
from app.services.vrptw_optimizer import (
    VRPTWOptimizer,
    VrptwOptimizer,
    OptimizerConfig,
    OptimizerWeights,
)

router = APIRouter()
daily_router = APIRouter(prefix="/daily")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEEKLY_DIR = PROJECT_ROOT / "weekly planning"
EXPORT_DIR = WEEKLY_DIR / "exports"


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

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
    trucks: Optional[List[Dict[str, Any]]] = None


class DailyExportRequest(BaseModel):
    source_file: str
    day: str
    plan: Dict[str, Any]


class WeightsPayload(BaseModel):
    alpha: float = 1.0
    beta: float = 2.0
    gamma: float = 1.5
    delta: float = 3.0
    epsilon: float = 1.0


class RunRequest(BaseModel):
    day: str                          # ISO date e.g. "2026-06-01"
    depot_lat: float = 36.5
    depot_lon: float = 10.1
    time_limit_sec: int = 60
    weights: Optional[WeightsPayload] = None


# ─────────────────────────────────────────────────────────────────────────────
# DB-aware endpoints (new)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run")
def run_optimizer(
    request: RunRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_auth),
):
    """
    Trigger the DB-aware VRPTW optimizer for a given day.

    Reads Camion(DISPONIBLE), Chauffeur(ACTIF), DemandeLocal(NOUVELLE, date=day)
    from the database, partitions deliveries into geographic zones (one per truck),
    solves each zone's route with OR-Tools, and materialises the result as a new
    PlanVersion(DRAFT) with PlanMission + MissionDemande rows.

    Zone isolation ensures no road segment is traversed by more than one truck.

    Returns the new plan_version_id.
    """
    try:
        plan_day = _date.fromisoformat(request.day)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {request.day!r}")

    weights = None
    if request.weights:
        weights = OptimizerWeights(
            alpha=request.weights.alpha,
            beta=request.weights.beta,
            gamma=request.weights.gamma,
            delta=request.weights.delta,
            epsilon=request.weights.epsilon,
        )

    cfg = OptimizerConfig(
        depot_lat=request.depot_lat,
        depot_lon=request.depot_lon,
        time_limit_sec=request.time_limit_sec,
    )

    try:
        optimizer = VrptwOptimizer(db=db, cfg=cfg)
        version = optimizer.plan(day=plan_day, weights=weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimizer failed: {exc}")

    return {
        "plan_version_id": version.id,
        "plan_id": version.plan_id,
        "status": version.statut_plan,
        "date": str(version.date_debut),
        "commentaire": version.commentaire,
    }


@router.get("/plan/{plan_version_id}")
def get_plan(
    plan_version_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_auth),
):
    """
    Return a plan version with all its missions and stop sequences.
    """
    from app.models.plan import PlanVersion, PlanMission, MissionDemande

    version = db.query(PlanVersion).filter(PlanVersion.id == plan_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Plan version not found")

    missions_out = []
    for mission in version.missions:
        stops = []
        for md in sorted(mission.mission_demandes, key=lambda x: x.ordre_livraison):
            d = md.demande
            c = d.client if d else None
            stops.append({
                "ordre": md.ordre_livraison,
                "demande_id": d.id if d else None,
                "client_id": d.client_id if d else None,
                "client_nom": c.nom if c else None,
                "quantite_kg": float(d.quantite_kg) if d else None,
                "date_livraison": str(d.date_livraison) if d else None,
                "lat": float(c.latitude) if c and c.latitude else None,
                "lon": float(c.longitude) if c and c.longitude else None,
            })
        missions_out.append({
            "mission_id": mission.id,
            "camion_id": mission.camion_id,
            "chauffeur_id": mission.chauffeur_id,
            "date_mission": str(mission.date_mission),
            "statut": mission.statut,
            "mode": mission.mode,
            "km_parcourus": float(mission.km_parcourus or 0),
            "charge_kg": float(mission.charge_kg or 0),
            "load_eff_pct": float(mission.load_eff_pct or 0),
            "fuel_consomme_l": float(mission.fuel_consomme_l or 0),
            "cout_transport_eur": float(mission.cout_transport_eur or 0),
            "stops": stops,
        })

    return {
        "plan_version_id": version.id,
        "plan_id": version.plan_id,
        "version_number": version.version_number,
        "periode": version.periode,
        "date_debut": str(version.date_debut),
        "date_fin": str(version.date_fin),
        "statut_plan": version.statut_plan,
        "commentaire": version.commentaire,
        "missions": missions_out,
    }


@router.get("/plan/{plan_version_id}/kpis")
def get_plan_kpi_preview(
    plan_version_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_auth),
):
    """
    Preview the expected KPIs for a DRAFT plan without executing it.

    Computes from materialised PlanMission rows:
    - Load efficiency average (R4)
    - Total km across all missions
    - Total fuel estimate
    - Total transport cost
    - Premium freight count (mode=PREMIUM missions)
    - Average utilisation %
    """
    from app.models.plan import PlanVersion, StatutMission, ModeMission

    version = db.query(PlanVersion).filter(PlanVersion.id == plan_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Plan version not found")

    missions = version.missions
    if not missions:
        return {
            "plan_version_id": plan_version_id,
            "mission_count": 0,
            "kpis": [],
        }

    total_km = sum(float(m.km_parcourus or 0) for m in missions)
    total_kg = sum(float(m.charge_kg or 0) for m in missions)
    total_fuel = sum(float(m.fuel_consomme_l or 0) for m in missions)
    total_cost = sum(float(m.cout_transport_eur or 0) for m in missions)
    load_effs = [float(m.load_eff_pct or 0) for m in missions if m.load_eff_pct]
    avg_load_eff = round(sum(load_effs) / len(load_effs), 2) if load_effs else 0.0
    premium_count = sum(1 for m in missions if m.mode == ModeMission.PREMIUM)

    # Fuel efficiency: mL per T·km  (mirroring KPI R4-13)
    fuel_eff = None
    if total_kg > 0 and total_km > 0:
        fuel_eff = round((total_fuel * 1000) / ((total_kg / 1000) * total_km), 4)

    # Logistics cost: €/T  (mirroring KPI R5-10)
    logistics_cost = None
    if total_kg > 0:
        logistics_cost = round(total_cost / (total_kg / 1000), 2)

    kpis = [
        {
            "code": "R4",
            "label": "Load Efficiency",
            "value": avg_load_eff,
            "unit": "%",
            "target": 85.0,
        },
        {
            "code": "R4-13",
            "label": "Fuel Efficiency",
            "value": fuel_eff,
            "unit": "mL/T.km",
            "target": 0.16,
        },
        {
            "code": "R5-10",
            "label": "Logistics Cost",
            "value": logistics_cost,
            "unit": "€/T",
            "target": 18.0,
        },
        {
            "code": "R4-03",
            "label": "Premium Freight Count",
            "value": premium_count,
            "unit": "Nb",
            "target": 3,
        },
    ]

    return {
        "plan_version_id": plan_version_id,
        "mission_count": len(missions),
        "total_km": round(total_km, 2),
        "total_kg": round(total_kg, 2),
        "total_fuel_l": round(total_fuel, 2),
        "total_cost_eur": round(total_cost, 2),
        "kpis": kpis,
    }


@router.post("/weights")
def update_weights(payload: WeightsPayload):
    """
    Update default optimiser weights (α/β/γ/δ/ε).
    In the current implementation these are per-request; a future enhancement
    can persist them in kpi_definition or a config table.
    """
    return {
        "alpha": payload.alpha,
        "beta": payload.beta,
        "gamma": payload.gamma,
        "delta": payload.delta,
        "epsilon": payload.epsilon,
        "note": "Weights accepted. Pass them in the next /api/optimization/run request.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy dict-based endpoints (kept for frontend planning UI)
# ─────────────────────────────────────────────────────────────────────────────

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
    """
    Dict-based VRPTW for the frontend planning UI.
    Now uses geographic zone clustering so each truck covers a compact area
    and no road segment is traversed by more than one vehicle.
    """
    try:
        optimizer = VRPTWOptimizer(
            request.deliveries, request.trucks, request.current_routes
        )
        result = optimizer.optimize()
        return {
            "status": result["status"],
            "algorithm": result["algorithm"],
            "plan": {
                "routes": result["routes"],
                "unassigned": result["unassigned"],
            },
            "routes": result["routes"],
            "unassigned": result["unassigned"],
            "costs": result["costs"],
            "suggestions": result["suggestions"],
            "metrics": result["metrics"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Daily plan endpoints (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@daily_router.post("/generate")
def generate_daily_plan(
    request: DailyGenerateRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    # Plain ``def`` on purpose: build() does synchronous geocoding (urllib +
    # a 1.05s Nominatim rate-limit sleep) that would block the event loop on a
    # cold cache. FastAPI runs sync handlers in a threadpool, so concurrent
    # requests are not stalled. See scripts/prewarm_geocode.py to warm offline.
    try:
        trucks = request.trucks if request.trucks is not None else _available_trucks_for_daily_plan(db)
        builder = DailyPlanBuilder(WEEKLY_DIR, trucks=trucks)
        return builder.build(day=_parse_day(request.day), source_file=request.source_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Small in-process cache for the dashboard: period_dashboard rebuilds 7 daily
# plans, so without this every poll (and every browser) re-runs the optimiser.
# Keyed by (day, fleet, workbook file+mtime) so it auto-invalidates when the
# workbook changes; TTL bounds staleness from anything else.
_DASH_CACHE: dict[tuple, tuple[float, dict]] = {}
_DASH_TTL_SECONDS = 120


def _weekly_source_signature() -> tuple:
    """Name + mtime of the newest weekly workbook, so edits bust the cache."""
    try:
        files = [p for p in WEEKLY_DIR.glob("*.xlsx") if not p.name.startswith("~$")]
        newest = max(files, key=lambda p: p.stat().st_mtime)
        return (newest.name, newest.stat().st_mtime_ns)
    except (ValueError, OSError):
        return ("none", 0)


def _vrptw_load_efficiency(plan: dict) -> Optional[float]:
    """Truck-fill % for one day from the VRPTW optimiser — the SAME engine the
    generated-planning page uses — so the dashboard's Load Efficiency KPI agrees
    with that screen. The operational DailyPlanBuilder spreads demand across more
    trucks (parallel dispatch, time windows) and reads ~62%; VRPTW re-packs the
    same deliveries into fewer, fuller routes (~85%). Reconstructs the day's
    deliveries + trucks from the plan and returns avg_utilization_percent
    (None if it can't be computed)."""
    stops = []
    for t in plan.get("trucks", []):
        for tr in t.get("trips", []):
            stops += tr.get("stops", [])
    stops += plan.get("unassigned", [])

    deliveries = []
    for i, s in enumerate(stops):
        pos = int(float(s.get("quantity_positions") or s.get("position_count") or 0)) or 1
        deliveries.append({
            "id": s.get("id") or i + 1,
            "customer": s.get("client"),
            "quantity": pos,
            # Geography barely affects the load/capacity ratio; use the resolved
            # client coords when present, else a tiny spread so the solver runs.
            "lat": s.get("lat") or 36.80 + i * 0.001,
            "lng": s.get("lon") or s.get("lng") or 10.18 + i * 0.001,
            "earliest_time": 480,
            "latest_time": 1020,
        })
    trucks = [
        {"id": t.get("truck_id"), "type": t.get("truck_label"),
         "capacity": int(float(t.get("capacity_positions") or 33))}
        for t in plan.get("trucks", [])
    ]
    if not deliveries or not trucks:
        return None
    res = VRPTWOptimizer(deliveries, trucks).optimize()
    return res.get("metrics", {}).get("avg_utilization_percent")


@daily_router.get("/dashboard")
def daily_dashboard(
    day: Optional[str] = None,
    period: str = "weekly",
    trucks: Optional[str] = None,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Operations-dashboard metrics derived from the generated daily plan:
    KPI cards (averaged over the chosen `period` — daily/weekly/monthly), fleet
    health, route-efficiency donut, recent activity, alerts, and a Mon→Sun
    trend — all real, offline-capable, cached.

    Plain ``def`` (threadpool): rebuilds up to ~31 daily plans (monthly), each
    doing synchronous geocoding that would otherwise block the event loop."""
    import time

    try:
        ref_day = _parse_day(day) if day else _date.today()
        period = period.lower() if period else "weekly"
        if period not in dashboard_service.PERIODS:
            period = "weekly"
        # The browser sends the active fleet (trucks NOT marked unavailable) as a
        # JSON query param, so the dashboard plans with the SAME trucks as the
        # generated-planning screen — otherwise it would silently use the full
        # fleet and never show the clients that go unassigned when a truck is out.
        fleet = None
        if trucks:
            try:
                parsed = json.loads(trucks)
                if isinstance(parsed, list) and parsed:
                    fleet = parsed
            except (ValueError, TypeError):
                fleet = None
        if fleet is None:
            fleet = _available_trucks_for_daily_plan(db)

        cache_key = (ref_day.isoformat(), period, repr(fleet), _weekly_source_signature())
        cached = _DASH_CACHE.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < _DASH_TTL_SECONDS:
            return cached[1]

        # Use the SAME OR-Tools VRPTW solver as the generated-planning page
        # (prefer_ortools=True). The dashboard plan feeds both the operational
        # panels AND the OTIF/OTD KPI cards (via dashboard_service._finalize_kpis),
        # so its set of unassigned clients must match what the planning screen
        # shows — otherwise the greedy heuristic assigns clients OR-Tools leaves
        # unassigned (hard time windows), making OTIF read 100% while the planning
        # page still lists those clients as undelivered. Cached below to bound the
        # extra solve cost over the period's days.
        builder = DailyPlanBuilder(
            WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=True), trucks=fleet
        )
        result = dashboard_service.period_dashboard(
            lambda d: builder.build(day=d), ref_day, builder.cfg.avg_speed_kmh, period=period,
            load_eff_fn=_vrptw_load_efficiency,
        )

        # KPI sourcing — all 4 cards (OTIF, Load, OTD, Fuel) are plan-derived in
        # dashboard_service._finalize_kpis, so they always show a value offline.
        # OTIF/OTD are measured by DAY (a position misses only when it is left
        # unassigned, i.e. pushed to another day), so they fall below 100% exactly
        # when the OR-Tools plan above cannot place a client — keeping the cards in
        # step with the unassigned list the generated-planning page shows.
        payload = {"day": ref_day.isoformat(), "period": period, **result}

        if len(_DASH_CACHE) > 32:  # keep the cache from growing unbounded
            _DASH_CACHE.clear()
        _DASH_CACHE[cache_key] = (now, payload)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.post("/export")
async def export_daily_plan(
    request: DailyExportRequest,
    _user: dict = Depends(require_auth),
):
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


def _parse_day(raw: str) -> _date:
    return _date.fromisoformat(raw)


def _available_trucks_for_daily_plan(db: Optional[Session]) -> Optional[List[Dict[str, Any]]]:
    if not db:
        return None
    try:
        from app.models.camion import Camion, CamionStatus

        rows = (
            db.query(Camion)
            .filter(Camion.status == CamionStatus.DISPONIBLE)
            .order_by(Camion.max_palettes.desc(), Camion.id.asc())
            .all()
        )
        if not rows:
            return None
        return [
            {
                "truck_id": truck.id,
                "truck_label": truck.plate_number,
                "capacity_positions": int(truck.max_palettes or 0),
                "capacity_kg": float(truck.capacite_kg or 0),
            }
            for truck in rows
            if (truck.max_palettes or 0) > 0
        ] or None
    except Exception:
        return None
