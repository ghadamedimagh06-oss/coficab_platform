from copy import deepcopy
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_db_optional
from app.services.daily_plan_builder import DailyPlanBuilder
from app.services.excel_exporter import export_plan_to_xlsx
from app.services.geo_service import GeoService
from app.services.osrm_service import OSRMError, OSRMService
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


class DailyRecalculateRequest(BaseModel):
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
def run_optimizer(request: RunRequest, db: Session = Depends(get_db)):
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
def get_plan(plan_version_id: int, db: Session = Depends(get_db)):
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
def get_plan_kpi_preview(plan_version_id: int, db: Session = Depends(get_db)):
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
    try:
        depot = GeoService().depot()
        stops = [_delivery_coordinate(delivery) for delivery in request.deliveries]
        if not stops:
            raise ValueError("At least one delivery with coordinates is required")
        route = OSRMService().route([depot] + stops + [depot])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSRMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "optimized",
        "deliveries": len(request.deliveries),
        "trucks": len(request.trucks),
        "route": route,
        "optimized_distance": route["total_distance_km"],
        "optimized_travel_min": route["total_travel_min"],
    }


def _delivery_coordinate(delivery: Dict[str, Any]) -> tuple[float, float]:
    lat = delivery.get("lat")
    lon = delivery.get("lon", delivery.get("lng"))
    if lat is None or lon is None:
        label = delivery.get("client") or delivery.get("customer") or delivery.get("id") or "delivery"
        raise ValueError(f"Missing coordinates for {label}")
    return float(lat), float(lon)


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
async def generate_daily_plan(
    request: DailyGenerateRequest,
    db: Optional[Session] = Depends(get_db_optional),
):
    try:
        trucks = request.trucks if request.trucks is not None else _available_trucks_for_daily_plan(db)
        builder = DailyPlanBuilder(WEEKLY_DIR, trucks=trucks)
        return builder.build(day=_parse_day(request.day), source_file=request.source_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.post("/recalculate")
async def recalculate_daily_plan(request: DailyRecalculateRequest):
    try:
        return _recalculate_daily_plan_routes(request.plan)
    except OSRMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


def _parse_day(raw: str) -> _date:
    return _date.fromisoformat(raw)


def _recalculate_daily_plan_routes(plan: Dict[str, Any]) -> Dict[str, Any]:
    recalculated = deepcopy(plan)
    osrm = OSRMService()
    depot = _plan_depot(recalculated)
    work_start = _minutes((recalculated.get("work_window") or {}).get("start")) or 6 * 60

    for truck in recalculated.get("trucks") or []:
        for trip in truck.get("trips") or []:
            stops = trip.get("stops") or []
            if not stops:
                continue

            coords = []
            missing = []
            for stop in stops:
                coord = _stop_coordinate(stop)
                if coord is None:
                    missing.append(stop.get("client") or stop.get("id") or "stop")
                else:
                    coords.append(coord)

            if missing:
                _mark_route_pending(trip, f"Missing coordinates for {', '.join(map(str, missing))}")
                continue

            try:
                route = osrm.route([depot] + coords + [depot])
            except OSRMError as exc:
                _mark_route_pending(trip, str(exc), status="unrouteable")
                continue

            legs = route.get("legs") or []
            if len(legs) < len(stops) + 1:
                _mark_route_pending(trip, "OSRM route response did not include all route legs", status="unrouteable")
                continue

            first_anchor = _minutes(stops[0].get("etd"))
            first_travel = int(legs[0].get("travel_min") or 0)
            depart_min = _minutes(trip.get("depart_at"))
            if first_anchor is not None:
                depart_min = max(work_start, first_anchor - first_travel)
            elif depart_min is None:
                depart_min = work_start

            cursor = depart_min
            total_service = 0
            for index, stop in enumerate(stops):
                leg = legs[index]
                travel = int(leg.get("travel_min") or 0)
                arrival = cursor + travel
                waiting = 0

                window = (stop.get("constraints") or {}).get("time_window")
                if isinstance(window, list) and len(window) == 2:
                    win_start = _minutes(window[0])
                    if win_start is not None and arrival < win_start:
                        waiting = win_start - arrival
                        arrival = win_start

                service = _handling_minutes(stop)
                departure = arrival + service
                total_service += service

                stop["etd"] = _clock(arrival)
                stop["eta"] = _clock(departure)
                stop["travel_min"] = travel
                stop["service_min"] = service
                stop["waiting_min"] = waiting
                stop["distance_km"] = round(float(leg.get("distance_km") or 0), 1)
                cursor = departure

            return_leg = legs[len(stops)]
            return_travel = int(return_leg.get("travel_min") or 0)
            trip["depart_at"] = _clock(depart_min)
            trip["return_at"] = _clock(cursor + return_travel)
            trip["return_travel_min"] = return_travel
            trip["total_distance_km"] = route["total_distance_km"]
            trip["total_travel_min"] = route["total_travel_min"]
            trip["total_service_min"] = total_service
            trip["total_duration_min"] = route["total_travel_min"] + total_service
            trip["geometry"] = route.get("geometry")
            trip["legs"] = legs
            trip["route_status"] = "osrm"
            trip.pop("route_error", None)

    return recalculated


def _plan_depot(plan: Dict[str, Any]) -> tuple[float, float]:
    depot = plan.get("depot") or {}
    lat = depot.get("lat")
    lon = depot.get("lon")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return GeoService().depot()


def _stop_coordinate(stop: Dict[str, Any]) -> Optional[tuple[float, float]]:
    lat = stop.get("lat")
    lon = stop.get("lon", stop.get("lng"))
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def _handling_minutes(stop: Dict[str, Any]) -> int:
    override = stop.get("handling_minutes") or stop.get("service_minutes")
    if override is not None:
        try:
            return max(0, int(round(float(override))))
        except (TypeError, ValueError):
            pass
    existing = stop.get("service_min")
    if existing is not None:
        try:
            return max(0, int(round(float(existing))))
        except (TypeError, ValueError):
            pass
    positions = stop.get("quantity_positions", stop.get("position_count", 0))
    try:
        return max(0, int(round(float(positions or 0) * 5.0)))
    except (TypeError, ValueError):
        return 0


def _mark_route_pending(trip: Dict[str, Any], reason: str, status: str = "manual_pending") -> None:
    trip["route_status"] = status
    trip["route_error"] = reason
    for key in (
        "total_distance_km",
        "total_travel_min",
        "total_service_min",
        "total_duration_min",
        "geometry",
        "legs",
    ):
        trip.pop(key, None)


def _minutes(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        hours, minutes = text.split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except (ValueError, TypeError):
        return None


def _clock(minutes: int) -> str:
    minutes = max(0, min(int(round(minutes)), 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


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
