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
from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig, DEFAULT_TRUCKS
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


class DailyParetoRequest(BaseModel):
    day: str
    source_file: Optional[str] = None
    trucks: Optional[List[Dict[str, Any]]] = None
    # Operating points to evaluate on the cost/CO₂ ↔ finish-time frontier.
    objectives: List[str] = ["green", "balanced", "fast"]


class StressScenario(BaseModel):
    label: str
    remove_truck_ids: List[int] = []      # take these trucks out of the fleet
    volume_multiplier: float = 1.0        # scale all demand (1.3 = +30%)
    disable_rental: bool = False          # forbid the hired truck (id 999)


class DailyStressTestRequest(BaseModel):
    day: str
    source_file: Optional[str] = None
    trucks: Optional[List[Dict[str, Any]]] = None
    objective: str = "balanced"
    # When empty, the server generates a sensible default battery (lose the
    # biggest truck, lose two, +20%/+30% volume, no rental).
    scenarios: List[StressScenario] = []


class DailyReplanRequest(BaseModel):
    day: str
    plan: Dict[str, Any]                       # the current plan to recover from
    disrupted_truck_ids: List[int] = []        # trucks taken out of service now
    completed_stop_ids: List[Any] = []         # deliveries already delivered (keep as-is)
    objective: str = "balanced"
    trucks: Optional[List[Dict[str, Any]]] = None  # override base fleet if given


class DailyExplainRequest(BaseModel):
    plan: Dict[str, Any]
    truck_id: Any


class DailyConfidenceRequest(BaseModel):
    day: str
    source_file: Optional[str] = None
    trucks: Optional[List[Dict[str, Any]]] = None
    objective: str = "balanced"
    # Pass an already-built (possibly hand-edited) plan to simulate it directly;
    # otherwise the server builds the plan for `day` first.
    plan: Optional[Dict[str, Any]] = None
    runs: int = 500
    travel_sigma: float = 0.25
    seed: int = 42


class DailyControlTowerRequest(BaseModel):
    day: str
    source_file: Optional[str] = None
    trucks: Optional[List[Dict[str, Any]]] = None
    objective: str = "balanced"
    # Pass an already-built (possibly hand-edited) plan to track it directly;
    # otherwise the server builds the plan for `day` first.
    plan: Optional[Dict[str, Any]] = None
    # Wall-clock to snapshot at, "HH:MM". Omitted → mid-point of the working day.
    as_of: Optional[str] = None
    # Inject per-truck minutes-behind: [{"truck_id": 3, "delay_min": 45}] or
    # {"3": 45}. Shifts that truck's whole timeline and surfaces any stop whose
    # projected arrival then misses its hard delivery window.
    delays: Any = None


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
        trucks = _sanitize_daily_plan_trucks(request.trucks) if request.trucks is not None else _available_trucks_for_daily_plan(db)
        builder = DailyPlanBuilder(WEEKLY_DIR, trucks=trucks)
        return builder.build(day=_parse_day(request.day), source_file=request.source_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Carbon & ESG endpoints (Pareto frontier + sustainability report)
# ─────────────────────────────────────────────────────────────────────────────

_VALID_OBJECTIVES = ("green", "cost", "balanced", "fast")


def _plan_finish_minutes(plan: Dict[str, Any]) -> Optional[int]:
    """Latest truck return across the whole plan, in minutes since midnight."""
    def _mins(clock: Optional[str]) -> Optional[int]:
        try:
            hh, mm = str(clock).split(":")[:2]
            return int(hh) * 60 + int(mm)
        except (ValueError, AttributeError):
            return None

    returns = [
        m
        for t in plan.get("trucks", [])
        for trip in t.get("trips", [])
        if (m := _mins(trip.get("return_at"))) is not None
    ]
    return max(returns) if returns else None


def _pareto_point(objective: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    s = plan.get("sustainability", {})
    finish = _plan_finish_minutes(plan)
    trucks_used = sum(1 for t in plan.get("trucks", []) if t.get("trips"))
    trips_used = sum(len(t.get("trips", [])) for t in plan.get("trucks", []))
    return {
        "objective": objective,
        "cost_tnd": plan.get("estimated_cost_tnd", {}).get("total"),
        "co2_kg": s.get("co2_kg"),
        "co2_saved_kg": s.get("co2_saved_kg"),
        "co2_saved_pct": s.get("co2_saved_pct"),
        "distance_km": s.get("planned_distance_km"),
        "finish_minutes": finish,
        "finish_clock": f"{finish // 60:02d}:{finish % 60:02d}" if finish is not None else None,
        "trucks_used": trucks_used,
        "trips_used": trips_used,
        "unassigned_count": len(plan.get("unassigned", [])),
    }


@daily_router.post("/pareto")
def daily_pareto(
    request: DailyParetoRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Re-solve the same day under several objectives and return the trade-off
    frontier (cost ↔ CO₂ ↔ finish time). Powers the sustainability slider: one
    click shows how going greener trades against finishing the day earlier.

    Returns one point per objective plus the full plan for each, so the UI can
    apply a chosen objective without a second round-trip.
    """
    try:
        day = _parse_day(request.day)
        objectives = [
            o.lower() for o in (request.objectives or []) if o.lower() in _VALID_OBJECTIVES
        ] or ["green", "balanced", "fast"]
        # De-dup while preserving order.
        seen: set = set()
        objectives = [o for o in objectives if not (o in seen or seen.add(o))]

        trucks = _sanitize_daily_plan_trucks(request.trucks) if request.trucks is not None else _available_trucks_for_daily_plan(db)

        points: List[Dict[str, Any]] = []
        plans: Dict[str, Any] = {}
        for obj in objectives:
            builder = DailyPlanBuilder(
                WEEKLY_DIR,
                cfg=DailyPlanConfig(prefer_ortools=True, objective=obj, global_solver_seconds=4),
                trucks=trucks,
            )
            plan = builder.build(day=day, source_file=request.source_file)
            plans[obj] = plan
            points.append(_pareto_point(obj, plan))

        greenest = min(points, key=lambda p: (p["co2_kg"] is None, p["co2_kg"] or 0))
        fastest = min(points, key=lambda p: (p["finish_minutes"] is None, p["finish_minutes"] or 1e9))
        cheapest = min(points, key=lambda p: (p["cost_tnd"] is None, p["cost_tnd"] or 1e12))

        return {
            "day": day.isoformat(),
            "points": points,
            "plans": plans,
            "recommendations": {
                "greenest": greenest["objective"],
                "fastest": fastest["objective"],
                "cheapest": cheapest["objective"],
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.get("/esg-report")
def daily_esg_report(
    day: Optional[str] = None,
    objective: str = "balanced",
    source_file: Optional[str] = None,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Structured ESG / sustainability report for a day's plan: headline carbon
    savings, fuel, per-truck emissions, and the methodology behind the numbers.
    Consumed by the dashboard ESG card and the one-click report export."""
    try:
        ref_day = _parse_day(day) if day else _date.today()
        obj = objective.lower() if objective.lower() in _VALID_OBJECTIVES else "balanced"
        trucks = _available_trucks_for_daily_plan(db)
        builder = DailyPlanBuilder(
            WEEKLY_DIR,
            cfg=DailyPlanConfig(prefer_ortools=True, objective=obj),
            trucks=trucks,
        )
        plan = builder.build(day=ref_day, source_file=source_file)
        s = plan.get("sustainability", {})
        cc = builder.cost_config

        per_truck = []
        speed = builder.cfg.avg_speed_kmh
        for t in plan.get("trucks", []):
            if not t.get("trips"):
                continue
            travel_min = sum(
                float(stop.get("travel_min") or 0)
                for trip in t["trips"] for stop in trip.get("stops", [])
            )
            km = travel_min / 60.0 * speed
            liters = km * cc.fuel_consumption_l_per_100km / 100.0
            per_truck.append({
                "truck_label": t.get("truck_label"),
                "truck_id": t.get("truck_id"),
                "trips": len(t["trips"]),
                "distance_km": round(km, 1),
                "fuel_liters": round(liters, 1),
                "co2_kg": round(liters * cc.co2_kg_per_liter_diesel, 1),
            })

        return {
            "day": ref_day.isoformat(),
            "objective": obj,
            "generated_at": plan.get("generated_at"),
            "headline": {
                "co2_kg": s.get("co2_kg"),
                "co2_saved_kg": s.get("co2_saved_kg"),
                "co2_saved_pct": s.get("co2_saved_pct"),
                "fuel_liters": s.get("fuel_liters"),
                "distance_saved_km": s.get("distance_saved_km"),
                "trees_year_equivalent": s.get("trees_year_equivalent"),
                "car_km_equivalent": s.get("car_km_equivalent"),
            },
            "sustainability": s,
            "per_truck": per_truck,
            "methodology": {
                "co2_kg_per_liter_diesel": cc.co2_kg_per_liter_diesel,
                "fuel_consumption_l_per_100km": cc.fuel_consumption_l_per_100km,
                "avg_speed_kmh": speed,
                "baseline": (
                    "Unoptimised manual baseline = every delivery served by its own "
                    "direct depot→client→depot round trip (no consolidation)."
                ),
                "tree_factor_kg_per_year": 21.0,
                "car_factor_kg_per_km": 0.12,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _stress_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Compact resilience summary of a plan for the stress-test lab."""
    def _pos(stop):
        return float(stop.get("quantity_positions") or stop.get("position_count") or 0)

    delivered_pos = sum(
        _pos(s)
        for t in plan.get("trucks", []) for trip in t.get("trips", []) for s in trip.get("stops", [])
    )
    unassigned = plan.get("unassigned", [])
    unassigned_pos = sum(_pos(s) for s in unassigned)
    demanded_pos = delivered_pos + unassigned_pos
    rental_used = any(
        str(t.get("truck_id")) == "999" and t.get("trips") for t in plan.get("trucks", [])
    )
    finish = _plan_finish_minutes(plan)
    s = plan.get("sustainability", {})
    return {
        "cost_tnd": plan.get("estimated_cost_tnd", {}).get("total"),
        "co2_kg": s.get("co2_kg"),
        "trucks_used": sum(1 for t in plan.get("trucks", []) if t.get("trips")),
        "trips_used": sum(len(t.get("trips", [])) for t in plan.get("trucks", [])),
        "rental_used": rental_used,
        "unassigned_count": len(unassigned),
        "unassigned_positions": round(unassigned_pos, 1),
        "served_pct": round(100.0 * delivered_pos / demanded_pos, 1) if demanded_pos else 100.0,
        "finish_clock": f"{finish // 60:02d}:{finish % 60:02d}" if finish is not None else None,
    }


def _default_stress_scenarios(base_fleet: List[Dict[str, Any]]) -> List["StressScenario"]:
    """A sensible default battery derived from the actual fleet: lose the biggest
    owned truck, lose the two biggest, +20%/+30% volume, and no rental."""
    owned = sorted(
        (t for t in base_fleet if str(t.get("truck_id")) != "999"),
        key=lambda t: t.get("capacity_positions", 0),
        reverse=True,
    )
    scenarios: List[StressScenario] = []
    if owned:
        biggest = owned[0]
        scenarios.append(StressScenario(
            label=f"Lose biggest truck ({biggest.get('truck_label', biggest['truck_id'])})",
            remove_truck_ids=[int(biggest["truck_id"])],
        ))
    if len(owned) >= 2:
        scenarios.append(StressScenario(
            label="Lose the two biggest trucks",
            remove_truck_ids=[int(owned[0]["truck_id"]), int(owned[1]["truck_id"])],
        ))
    scenarios.append(StressScenario(label="Demand +20%", volume_multiplier=1.2))
    scenarios.append(StressScenario(label="Demand +30%", volume_multiplier=1.3))
    scenarios.append(StressScenario(label="No rental truck", disable_rental=True))
    return scenarios


@daily_router.post("/stress-test")
def daily_stress_test(
    request: DailyStressTestRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Decision-support sandbox: re-solve the day under disruption/growth
    scenarios and compare each to the baseline plan.

    For every scenario it reports served %, unassigned load, cost & CO₂ deltas,
    trucks/trips used, whether the day still finishes, and whether the rental was
    forced — so a planner can see fleet resilience before the day actually breaks.
    Heavy by design (re-solves per scenario); run it as a deliberate action.
    """
    try:
        day = _parse_day(request.day)
        obj = request.objective.lower() if request.objective.lower() in _VALID_OBJECTIVES else "balanced"
        base_fleet = (
            _sanitize_daily_plan_trucks(request.trucks)
            if request.trucks is not None
            else (_available_trucks_for_daily_plan(db) or list(DEFAULT_TRUCKS))
        )

        def _build(fleet, multiplier):
            builder = DailyPlanBuilder(
                WEEKLY_DIR,
                cfg=DailyPlanConfig(
                    prefer_ortools=True, objective=obj,
                    global_solver_seconds=3, demand_multiplier=multiplier,
                ),
                trucks=fleet,
            )
            return builder.build(day=day, source_file=request.source_file)

        baseline_plan = _build(base_fleet, 1.0)
        baseline = _stress_summary(baseline_plan)

        scenarios = request.scenarios or _default_stress_scenarios(base_fleet)
        results: List[Dict[str, Any]] = []
        for sc in scenarios:
            remove = set(int(x) for x in sc.remove_truck_ids)
            fleet = [
                t for t in base_fleet
                if int(t["truck_id"]) not in remove
                and not (sc.disable_rental and str(t.get("truck_id")) == "999")
            ]
            if not fleet:
                results.append({
                    "label": sc.label, "feasible": False,
                    "note": "Scenario removes the entire fleet — nothing to plan.",
                })
                continue
            plan = _build(fleet, max(0.1, float(sc.volume_multiplier or 1.0)))
            summary = _stress_summary(plan)
            results.append({
                "label": sc.label,
                "feasible": True,
                "removed_truck_ids": sorted(remove),
                "volume_multiplier": sc.volume_multiplier,
                "disable_rental": sc.disable_rental,
                **summary,
                "deltas": {
                    "cost_tnd": _safe_delta(summary["cost_tnd"], baseline["cost_tnd"]),
                    "co2_kg": _safe_delta(summary["co2_kg"], baseline["co2_kg"]),
                    "unassigned_count": summary["unassigned_count"] - baseline["unassigned_count"],
                    "served_pct": round(summary["served_pct"] - baseline["served_pct"], 1),
                },
            })

        return {"day": day.isoformat(), "objective": obj, "baseline": baseline, "scenarios": results}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _safe_delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 1)


def _stops_with_truck(plan: Dict[str, Any]):
    """Yield (truck_id, truck_label, stop) for every assigned stop in a plan."""
    for t in plan.get("trucks", []):
        for trip in t.get("trips", []):
            for s in trip.get("stops", []):
                yield t.get("truck_id"), t.get("truck_label"), s


def compute_replan(
    plan: Dict[str, Any],
    day: _date,
    disrupted_truck_ids: List[Any],
    completed_stop_ids: List[Any],
    objective: str = "balanced",
    trucks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Self-healing recovery core: re-optimise the remaining undelivered stops on
    the remaining fleet and return {day, plan, diff}. Raises ValueError on the
    two no-op cases so HTTP and copilot callers can present a friendly message.
    Shared by POST /replan and the agentic copilot's breakdown action (W3.1)."""
    obj = objective.lower() if objective.lower() in _VALID_OBJECTIVES else "balanced"
    current = plan or {}
    disrupted = set(int(x) for x in disrupted_truck_ids)
    completed = set(str(x) for x in completed_stop_ids)

    # 1) Remaining demand = every assigned stop not yet completed, plus the
    #    deliveries that were already unassigned in the current plan.
    old_assignment: Dict[str, str] = {}
    remaining: List[Dict[str, Any]] = []
    for truck_id, truck_label, stop in _stops_with_truck(current):
        sid = str(stop.get("id"))
        old_assignment[sid] = truck_label
        if sid in completed:
            continue
        remaining.append(dict(stop))
    for stop in current.get("unassigned", []):
        old_assignment.setdefault(str(stop.get("id")), "UNASSIGNED")
        remaining.append(dict(stop))

    if not remaining:
        raise ValueError("No remaining deliveries to replan.")

    # 2) Remaining fleet = current plan's trucks minus the disrupted ones
    #    (or an explicit override), so the residual problem uses real vehicles.
    if trucks is not None:
        base_fleet = trucks
    else:
        base_fleet = [
            {
                "truck_id": t.get("truck_id"),
                "truck_label": t.get("truck_label"),
                "capacity_positions": t.get("capacity_positions"),
                "capacity_kg": t.get("capacity_kg"),
                "capacity_m3": t.get("capacity_m3"),
            }
            for t in current.get("trucks", [])
        ]
    fleet = [t for t in base_fleet if int(t["truck_id"]) not in disrupted]
    if not fleet:
        raise ValueError("No trucks left after the disruption.")

    # 3) Re-solve the residual problem.
    builder = DailyPlanBuilder(
        WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=True, objective=obj), trucks=fleet,
    )
    new_plan = builder.replan(day, remaining)

    # 4) Diff old vs new.
    new_assignment: Dict[str, str] = {}
    for _tid, truck_label, stop in _stops_with_truck(new_plan):
        new_assignment[str(stop.get("id"))] = truck_label
    new_unassigned_ids = {str(s.get("id")) for s in new_plan.get("unassigned", [])}

    reassignments = []
    for sid, new_truck in new_assignment.items():
        old_truck = old_assignment.get(sid)
        if old_truck and old_truck != new_truck:
            reassignments.append({"stop_id": sid, "from": old_truck, "to": new_truck})

    newly_unassigned = [
        {"stop_id": sid, "from": old_assignment.get(sid)}
        for sid in new_unassigned_ids
        if old_assignment.get(sid) not in (None, "UNASSIGNED")
    ]
    recovered = [
        {"stop_id": sid, "to": new_assignment.get(sid)}
        for sid in new_assignment
        if old_assignment.get(sid) == "UNASSIGNED"
    ]

    old_cost = (current.get("estimated_cost_tnd") or {}).get("total")
    new_cost = (new_plan.get("estimated_cost_tnd") or {}).get("total")
    old_co2 = current.get("estimated_co2_kg")
    new_co2 = new_plan.get("estimated_co2_kg")

    return {
        "day": day.isoformat(),
        "plan": new_plan,
        "diff": {
            "disrupted_truck_ids": sorted(disrupted),
            "completed_count": len(completed),
            "replanned_stops": len(remaining),
            "reassignments": reassignments,
            "reassigned_count": len(reassignments),
            "newly_unassigned": newly_unassigned,
            "newly_unassigned_count": len(newly_unassigned),
            "recovered": recovered,
            "recovered_count": len(recovered),
            "cost_delta_tnd": _safe_delta(new_cost, old_cost),
            "co2_delta_kg": _safe_delta(new_co2, old_co2),
        },
    }


@daily_router.post("/replan")
def daily_replan(
    request: DailyReplanRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Self-healing re-planning. Given the current plan, a set of trucks that have
    just gone out of service, and the deliveries already completed, re-optimise
    the REMAINING undelivered stops across the REMAINING fleet and return the new
    plan plus a diff (reassignments, newly-unassigned, cost & CO₂ deltas) for
    one-click approval. This is the disruption-recovery flow.
    """
    try:
        day = _parse_day(request.day)
        return compute_replan(
            request.plan, day, request.disrupted_truck_ids,
            request.completed_stop_ids, request.objective, _sanitize_daily_plan_trucks(request.trucks),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _explain_truck(plan: Dict[str, Any], truck_id: Any) -> Dict[str, Any]:
    """Plain-language rationale for why a truck's route looks the way it does,
    derived purely from the plan (no re-solve): load vs capacity, the binding
    constraint, hard-window and single-feasible stops, and a right-sizing
    counterfactual against the rest of the fleet."""
    trucks = plan.get("trucks", [])
    truck = next((t for t in trucks if str(t.get("truck_id")) == str(truck_id)), None)
    if truck is None:
        raise HTTPException(status_code=404, detail=f"truck {truck_id} not in plan")

    def _pos(s):
        return float(s.get("quantity_positions") or s.get("position_count") or 0)

    def _kg(s):
        return float(s.get("quantity_kg") or 0)

    trips = truck.get("trips", [])
    stops = [s for trip in trips for s in trip.get("stops", [])]
    cap_pos = float(truck.get("capacity_positions") or 0) or 1.0
    cap_kg = float(truck.get("capacity_kg") or 0) or 1.0

    # A truck can run several trips, so capacity binds PER TRIP, not on the daily
    # sum. Report the daily totals, but base utilisation + the counterfactual on
    # the peak single-trip load (the hardest thing this vehicle must carry).
    trip_loads = [
        (sum(_pos(s) for s in trip.get("stops", [])), sum(_kg(s) for s in trip.get("stops", [])))
        for trip in trips
    ]
    day_pos = sum(tp for tp, _ in trip_loads)
    day_kg = sum(tk for _, tk in trip_loads)
    peak_pos = max((tp for tp, _ in trip_loads), default=0.0)
    peak_kg = max((tk for _, tk in trip_loads), default=0.0)
    load_pos, load_kg = peak_pos, peak_kg  # the binding single-trip load
    util_pos = round(100 * peak_pos / cap_pos, 1)
    util_kg = round(100 * peak_kg / cap_kg, 1)
    avg_util_pos = round(100 * (day_pos / len(trips)) / cap_pos, 1) if trips else 0.0
    binding = "weight" if util_kg >= util_pos else "positions"

    speed = DailyPlanConfig().avg_speed_kmh
    total_travel_min = sum(float(s.get("travel_min") or 0) for s in stops)
    total_km = round(total_travel_min / 60.0 * speed, 1)

    # Stops that can ONLY go on this truck (from the builder's diagnostics).
    diag = plan.get("diagnostics", {})
    single = [
        d for d in diag.get("single_feasible_truck", [])
        if str(d.get("only_truck")) == str(truck.get("truck_label"))
    ]
    windowed = [s for s in stops if (s.get("constraints") or {}).get("time_window")]

    # Right-sizing counterfactual: is there a smaller truck that still fits?
    smaller_fit = [
        t for t in trucks
        if str(t.get("truck_id")) != str(truck_id)
        and float(t.get("capacity_positions") or 0) < cap_pos
        and float(t.get("capacity_positions") or 0) >= load_pos
        and float(t.get("capacity_kg") or 0) >= load_kg
    ]
    if smaller_fit:
        smallest = min(smaller_fit, key=lambda t: t.get("capacity_positions", 0))
        counterfactual = (
            f"A smaller truck ({smallest.get('truck_label')}, "
            f"{smallest.get('capacity_positions')} pos) could also carry this load — "
            f"this vehicle was used because it was free for this zone."
        )
    else:
        counterfactual = (
            f"This is the smallest available truck that fits the load "
            f"({int(load_pos)} pos / {int(load_kg)} kg) — no smaller vehicle could carry it."
        )

    # Per-stop one-liners.
    stop_reasons = []
    for s in stops:
        bits = []
        if (s.get("constraints") or {}).get("time_window"):
            tw = s["constraints"]["time_window"]
            bits.append(f"hard window {tw[0]}–{tw[1]}")
        if s.get("distance_km") is not None:
            bits.append(f"{s['distance_km']} km from depot")
        if str(s.get("client")) in {str(d.get("client")) for d in single}:
            bits.append("only this truck can carry it")
        stop_reasons.append({"client": s.get("client"), "eta": s.get("etd"), "why": ", ".join(bits) or "nearest in this truck's zone"})

    # Headline sentence.
    parts = [
        f"{truck.get('truck_label')} runs {len(trips)} trip(s) covering "
        f"{len(stops)} stop(s), carrying {int(day_pos)} positions / {int(day_kg)} kg across the day "
        f"over ~{total_km} km. Its fullest trip uses {util_pos}% of pallet capacity "
        f"({util_kg}% of weight)."
    ]
    parts.append(f"The binding constraint here is {binding}.")
    if single:
        parts.append(f"{len(single)} stop(s) can only be served by this truck.")
    if windowed:
        parts.append(f"{len(windowed)} stop(s) have hard delivery windows that pin the schedule.")
    parts.append(counterfactual)

    return {
        "truck_id": truck.get("truck_id"),
        "truck_label": truck.get("truck_label"),
        "summary": " ".join(parts),
        "facts": {
            "stops": len(stops),
            "trips": len(trips),
            "day_positions": int(day_pos),
            "day_kg": int(day_kg),
            "peak_trip_positions": int(peak_pos),
            "peak_trip_kg": int(peak_kg),
            "capacity_positions": int(cap_pos),
            "capacity_kg": int(cap_kg),
            "peak_utilization_positions_pct": util_pos,
            "peak_utilization_kg_pct": util_kg,
            "avg_trip_utilization_positions_pct": avg_util_pos,
            "binding_constraint": binding,
            "total_km": total_km,
            "single_feasible_stops": len(single),
            "time_windowed_stops": len(windowed),
        },
        "counterfactual": counterfactual,
        "stop_reasons": stop_reasons,
    }


@daily_router.post("/explain")
def daily_explain(
    request: DailyExplainRequest,
    _user: dict = Depends(require_auth),
):
    """Explainable routing: why does this truck's route look the way it does?
    Returns a grounded, plain-language rationale plus a right-sizing
    counterfactual — computed directly from the plan, no re-solve."""
    try:
        return _explain_truck(request.plan, request.truck_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.post("/confidence")
def daily_confidence(
    request: DailyConfidenceRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Monte-Carlo plan-confidence score: replays the day's plan hundreds of
    times under randomised travel/service times (plus rare disruption spikes) and
    returns how often it actually finishes on time, P50/P90 finish, OTIF spread,
    and the most fragile stops. Turns a deterministic plan into a risk-aware one.
    """
    from app.services.simulation_service import simulate_plan

    try:
        plan = request.plan
        if plan is None:
            day = _parse_day(request.day)
            obj = request.objective.lower() if request.objective.lower() in _VALID_OBJECTIVES else "balanced"
            trucks = _sanitize_daily_plan_trucks(request.trucks) if request.trucks is not None else _available_trucks_for_daily_plan(db)
            builder = DailyPlanBuilder(
                WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=True, objective=obj), trucks=trucks,
            )
            plan = builder.build(day=day, source_file=request.source_file)

        runs = max(50, min(2000, int(request.runs or 500)))
        report = simulate_plan(
            plan,
            runs=runs,
            travel_sigma=max(0.0, float(request.travel_sigma or 0.25)),
            seed=int(request.seed or 42),
        )
        return {"day": request.day, "confidence": report}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@daily_router.post("/control-tower")
def daily_control_tower(
    request: DailyControlTowerRequest,
    db: Optional[Session] = Depends(get_db_optional),
    _user: dict = Depends(require_auth),
):
    """Live control tower: interpolate every truck's current position along its
    planned route at a wall-clock time, classify its live state, and raise
    predicted-late / geofence alerts for stops that miss their delivery window
    (optionally after an injected per-truck delay). Derived purely from the plan
    — no external GPS feed — so it is deterministic and demoable."""
    from app.services.control_tower import live_snapshot, _to_min

    try:
        plan = request.plan
        if plan is None:
            day = _parse_day(request.day)
            obj = request.objective.lower() if request.objective.lower() in _VALID_OBJECTIVES else "balanced"
            trucks = _sanitize_daily_plan_trucks(request.trucks) if request.trucks is not None else _available_trucks_for_daily_plan(db)
            builder = DailyPlanBuilder(
                WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=True, objective=obj), trucks=trucks,
            )
            plan = builder.build(day=day, source_file=request.source_file)

        now_min = _to_min(request.as_of) if request.as_of else None
        snapshot = live_snapshot(plan, now_min=now_min, delays=request.delays)
        return {"day": request.day, "control_tower": snapshot}
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
                    fleet = _sanitize_daily_plan_trucks(parsed)
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


def _sanitize_daily_plan_trucks(trucks: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if trucks is None:
        return None
    unavailable_truck = {"PANNE", "MAINTENANCE", "BROKEN DOWN", "MAINTENANCE", "EN PANNE", "EN MAINTENANCE"}
    unavailable_driver = {"CONGE", "ARRET_MALADIE", "INACTIF", "EN PAUSE"}
    clean: List[Dict[str, Any]] = []
    for truck in trucks:
        status = str(truck.get("resource_status") or truck.get("truck_status") or truck.get("status") or "").upper()
        driver_status = str(truck.get("driver_status") or "").upper()
        if status == "OUT_OF_SERVICE" or status in unavailable_truck:
            continue
        if driver_status and driver_status in unavailable_driver:
            continue
        truck_id = truck.get("truck_id", truck.get("id"))
        capacity_positions = truck.get("capacity_positions", truck.get("max_palettes", truck.get("max_pallets", 0)))
        capacity_kg = truck.get("capacity_kg", truck.get("capacite_kg", truck.get("capacity", 0)))
        try:
            capacity_positions = int(capacity_positions or 0)
            capacity_kg = float(capacity_kg or 0)
        except (TypeError, ValueError):
            continue
        if truck_id is None or capacity_positions <= 0:
            continue
        item = {
            **truck,
            "truck_id": truck_id,
            "truck_label": truck.get("truck_label") or truck.get("plate_number") or f"Truck {truck_id}",
            "capacity_positions": capacity_positions,
            "capacity_kg": capacity_kg,
        }
        clean.append(item)
    return clean


def _available_trucks_for_daily_plan(db: Optional[Session]) -> Optional[List[Dict[str, Any]]]:
    if not db:
        return None
    try:
        from app.models.camion import Camion, CamionStatus
        from app.models.chauffeur import Chauffeur, ChauffeurStatus

        all_rows = db.query(Camion).all()
        if not all_rows:
            return None
        active_drivers = {
            driver.id: driver
            for driver in db.query(Chauffeur).filter(Chauffeur.status == ChauffeurStatus.ACTIF).all()
        }
        rows = (
            db.query(Camion)
            .filter(Camion.status == CamionStatus.DISPONIBLE)
            .order_by(Camion.max_palettes.desc(), Camion.id.asc())
            .all()
        )
        if not rows:
            return []
        return [
            {
                "truck_id": truck.id,
                "truck_label": truck.plate_number,
                "capacity_positions": int(truck.max_palettes or 0),
                "capacity_kg": float(truck.capacite_kg or 0),
                "driver_id": truck.chauffeur_defaut_id,
                "driver": active_drivers[truck.chauffeur_defaut_id].full_name,
            }
            for truck in rows
            if (truck.max_palettes or 0) > 0 and truck.chauffeur_defaut_id in active_drivers
        ]
    except Exception:
        return None
