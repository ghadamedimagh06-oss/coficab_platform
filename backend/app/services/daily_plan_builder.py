"""Generated daily planning builder.

Builds a realistic truck-by-time plan from the weekly-planning workbook:

  1. Parse the workbook rows for the requested day.
  2. Resolve every customer via the client directory (authoritative destination
     + real road km from the depot) with geocoded city coordinates.
  3. Build a travel-time matrix from distance ÷ average truck speed.
  4. Cluster deliveries into spatially compact zones — one truck per zone — so a
     truck never criss-crosses the country; nearby stops ride together.
  5. Order each zone's stops (OR-Tools TSP on real durations, greedy fallback),
     split into trips by position capacity, and schedule each stop with its real
     travel time, on-site service time, and Excel time-window constraints.

Each trip records depart_at / return_at for audit/export only. The Gantt no
longer turns those values into automatic red bars; dispatchers add manual
blocking markers when they want to reserve time visually. Customers that are
foreign export sites, or that cannot be geocoded, are returned as unassigned
with a reason rather than being given a fake slot.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.services.geo_service import GeoService, _haversine_km, ROAD_WINDING_FACTOR
from app.services.planning_service import PlanningService
from app.services.vrptw_optimizer import cluster_zones

log = logging.getLogger(__name__)


# capacity_m3 is the usable cargo VOLUME of each truck's deck. Cable reels are
# bulky: a load can "cube out" (run out of m³) before it hits the pallet-position
# or kg limit, so volume is a third, independent capacity dimension. The 14-pos
# rigid/box trucks carry ~40 m³ of deck; the 24-pos semi/curtainsider ~85–90 m³.
DEFAULT_TRUCKS = [
    {"truck_id": 1, "truck_label": "Truck 1", "capacity_positions": 14, "capacity_kg": 10_200, "capacity_m3": 40.0},
    {"truck_id": 2, "truck_label": "Truck 2", "capacity_positions": 14, "capacity_kg": 10_230, "capacity_m3": 40.0},
    {"truck_id": 3, "truck_label": "Truck 3", "capacity_positions": 14, "capacity_kg": 9_227, "capacity_m3": 40.0},
    {"truck_id": 4, "truck_label": "Truck 4", "capacity_positions": 14, "capacity_kg": 9_200, "capacity_m3": 40.0},
    {"truck_id": 5, "truck_label": "Truck 5", "capacity_positions": 24, "capacity_kg": 24_950, "capacity_m3": 90.0},
    {"truck_id": 6, "truck_label": "Truck 6", "capacity_positions": 14, "capacity_kg": 7_650, "capacity_m3": 40.0},
]

RENTAL_PROFILES = [
    {
        "profile": "LIGHT_5_PALLET",
        "vehicle_type": "Light / tourist vehicle",
        "capacity_positions": 5,
        "capacity_kg": 1_500,
        "capacity_m3": 15.0,
        "required_permit": "B",
        "fixed_cost_eur": 90,
        "cost_per_km_eur": 0.65,
    },
    {
        "profile": "HEAVY_TRUCK",
        "vehicle_type": "Heavy truck",
        "capacity_positions": 14,
        "capacity_kg": 10_000,
        "capacity_m3": 40.0,
        "required_permit": "C",
        "fixed_cost_eur": 180,
        "cost_per_km_eur": 1.15,
    },
    {
        "profile": "SEMI_TRAILER",
        "vehicle_type": "Semi-trailer",
        "capacity_positions": 24,
        "capacity_kg": 25_000,
        "capacity_m3": 90.0,
        "required_permit": "CE",
        "fixed_cost_eur": 300,
        "cost_per_km_eur": 1.55,
    },
]

PRIORITY_WEIGHT = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False


@dataclass
class DailyPlanConfig:
    work_start: str = "06:00"      # normal depot opening for regular trips
    # Long hauls may leave the depot before normal opening so the truck gets
    # home as early as possible — freeing it for a second tour.
    early_start: str = "05:00"
    long_haul_km: float = 120.0    # one-way depot distance treated as "long distance"
    work_end: str = "20:00"
    # Latest a truck may LEAVE the depot on a fresh trip. The binding daily
    # constraint is the departure, not the return: a driver heading to a far
    # zone (e.g. Ksar Hellal, Kairouan) is allowed to drive back after 20:00, so
    # the round trip is feasible as long as it departs by this cut-off.
    max_depart: str = "18:00"
    service_minutes: int = 20      # minimum on-site setup/(un)loading time
    service_minutes_per_position: float = 3.0
    max_service_minutes: int = 120
    reload_minutes: int = 30       # back at depot between trips of one truck
    avg_speed_kmh: float = 55.0    # loaded-truck average over Tunisian roads
    # Use OR-Tools for stop ordering. The single-day planning screen wants the
    # best route; the dashboard, which rebuilds a whole week per refresh, turns
    # this off and uses the (near-instant) greedy order so it stays responsive.
    prefer_ortools: bool = True
    # Use real road distances (OSRM /table) for the travel matrix instead of
    # straight-line × winding factor. Falls back to haversine automatically if
    # the routing server is unreachable, so builds never block on it.
    use_osrm_road_matrix: bool = True
    # Per-variant time budget for the global multi-vehicle VRPTW solve.
    global_solver_seconds: int = 6
    # Max trips one truck may run in a day (vehicle slots in the global model).
    trips_per_truck: int = 3

    # --- Objective shaping: operational policy, not money ------------------
    # The dispatcher's stated goal: finish the whole day as early as possible by
    # running trucks IN PARALLEL (each well filled), rather than a few trucks
    # doing many sequential trips. These three knobs encode that policy in the
    # solver objective; they are deliberately NOT in TND (that stays in
    # CostConfig / _cost_breakdown for the reported bill).
    #
    # Global makespan/balance term on the time dimension: rewards bringing the
    # LAST truck home sooner, so the solver spreads load across trucks instead
    # of queuing trips on a few. Higher => more parallelism / earlier finish.
    makespan_cost_coef: int = 3
    # Cost of opening a truck's FIRST trip. High enough that the solver won't
    # dispatch a truck for a near-empty load (keeps trucks ~full), low enough
    # that adding a truck for parallelism stays attractive. This is the soft
    # "fill the truck before opening another" / ~90% pressure.
    trip_dispatch_cost: int = 1000
    # Extra cost per SUBSEQUENT trip on the SAME truck, so a 2nd/3rd trip is
    # dearer than dispatching a fresh truck's first trip — favouring many
    # well-filled trucks over a few trucks doing a lot of trips.
    extra_trip_cost: int = 2500

    # --- Objective mode (Pareto axis: cost/CO₂ ↔ finish time) -------------
    # The makespan term above trades total distance (≈ fuel ≈ CO₂) against how
    # early the LAST truck gets home. `objective` selects an operating point on
    # that frontier without the caller having to know the raw coefficient:
    #   "green" / "cost" → minimise distance & CO₂ (fewest, fullest trucks; the
    #                       day may finish later), makespan weight 0;
    #   "balanced"       → the default makespan_cost_coef;
    #   "fast"           → maximise parallelism so the day finishes earliest
    #                       (more trucks, more km/CO₂), makespan weight boosted.
    objective: str = "balanced"

    # Coverage-first portfolio: when True (default), build() never abandons a
    # serviceable customer — green/cost always solve a small makespan portfolio
    # (and additionally minimise CO₂), while balanced/fast escalate to it only if
    # their single solve dropped a serviceable delivery. Set False for bulk/
    # latency-sensitive callers that accept a single solve (e.g. heavy batch jobs).
    coverage_portfolio: bool = True

    # --- Scenario / stress-test knob -------------------------------------
    # Scales every delivery's demanded positions and kg by this factor when the
    # plan is built. 1.0 = the workbook as-is; 1.3 = "what if volume is +30%?".
    # Used by the stress-test lab to probe fleet resilience without editing the
    # source workbook. Capacity, time windows and the fleet are untouched.
    demand_multiplier: float = 1.0

    # --- Volume / m³ capacity dimension (cable reels cube out) ------------
    # Reels are voluminous: a truck can run out of DECK VOLUME before it reaches
    # its pallet-position or kg limit. Volume is therefore modelled as a third,
    # independent capacity dimension alongside positions and gross weight.
    #   • A delivery's volume is its explicit ``volume_m3`` when the workbook
    #     provides one, else it is derived as positions × ``m3_per_position``.
    #   • Trucks declare ``capacity_m3``; the deck headroom on the default fleet
    #     is set so DERIVED volume never binds before positions (zero behaviour
    #     change on position-only data), while an explicitly bulky reel load is
    #     correctly constrained and, if it cubes out the biggest truck, dropped
    #     with a volume reason.
    # The whole dimension is a safe no-op for any truck set that does not declare
    # ``capacity_m3`` (e.g. ad-hoc fleets in tests), so it never invents a limit.
    enforce_volume: bool = True
    m3_per_position: float = 1.8   # usable deck volume of one stacked pallet position


@dataclass
class CostConfig:
    """Real-world cost parameters in TND (Tunisian Dinars).

    Defaults reflect COFICAB operating costs as of 2026. Injectable per
    deployment via ``DailyPlanBuilder(cost_config=...)`` so the same optimiser
    can be tuned per customer without code changes. The optimiser objective and
    the ``estimated_cost_tnd`` reported on every plan are both derived from
    these, so the score the solver minimises is the money the dispatcher sees.
    """
    fuel_price_tnd_per_liter: float = 2.2        # TND/L (Gasoil), 2026
    fuel_consumption_l_per_100km: float = 28.0   # avg poids lourd
    driver_hourly_cost_tnd: float = 8.5          # TND/h incl. charges
    truck_dispatch_fixed_tnd: float = 45.0       # fixed cost per owned-truck dispatch
    rental_truck_per_day_tnd: float = 420.0      # daily cost of the hired truck
    underutil_penalty_per_pos: float = 3.0       # opportunity cost per empty position
    unassigned_delivery_penalty_tnd: float = 2000.0  # per unassigned delivery
    urgent_unassigned_multiplier: float = 3.0    # multiplier for urgent unassigned
    # Diesel well-to-wheel emission factor: kg of CO₂ released per litre burned.
    # 2.68 kg/L is the widely used direct-combustion factor for road diesel; it
    # drives the sustainability/ESG reporting and the "green" objective.
    co2_kg_per_liter_diesel: float = 2.68


class DailyPlanBuilder:
    def __init__(
        self,
        source_dir: Path,
        cfg: Optional[DailyPlanConfig] = None,
        geo: Optional[GeoService] = None,
        trucks: Optional[list[dict[str, Any]]] = None,
        cost_config: Optional[CostConfig] = None,
        osrm: Optional[Any] = None,
    ):
        self.source_dir = source_dir
        self.cfg = cfg or DailyPlanConfig()
        self.geo = geo or GeoService()
        self.truck_templates = DEFAULT_TRUCKS if trucks is None else trucks
        self.cost_config = cost_config or CostConfig()
        self.osrm = osrm
        # Set transiently by the green CO₂ portfolio to override the makespan
        # coefficient for a single solve (see _build_min_co2).
        self._makespan_override: Optional[int] = None

    # Makespan coefficients tried by the coverage-first portfolio. They span the
    # frontier from pure consolidation (0) to full parallelism (12, = "fast"), so
    # the portfolio's coverage-first pick is never worse than any single operating
    # point — guaranteeing we never abandon a serviceable customer that some
    # setting could serve, and (for green) that CO₂ is genuinely minimised.
    _PORTFOLIO_COEFS = (0, 6, 12)

    # Substrings of unassigned reasons that are HARD / non-recoverable: re-solving
    # at a different makespan can never place these (foreign site, ungeocodable,
    # or larger than the biggest truck on some dimension). Any OTHER drop reason
    # (no feasible vehicle/time slot, working hours, time window, depart cut-off)
    # is a SERVICEABLE delivery the solver merely failed to fit — exactly what the
    # coverage-first portfolio exists to recover.
    _HARD_DROP_MARKERS = ("export", "could not locate", "exceeds the largest truck", "cubes out", "no available trucks")

    # ------------------------------------------------------------------ build
    def build(self, day: date, source_file: Optional[str] = None) -> dict[str, Any]:
        """Build the day's plan, never abandoning a serviceable customer.

        green/cost always run the coverage-first portfolio (they additionally want
        minimum CO₂). Other objectives do a single fast solve and only escalate to
        the portfolio if that solve dropped a SERVICEABLE delivery — so the common
        case stays one solve, and we only pay for extra solves when there is an
        actual coverage problem to fix. Disable entirely with
        DailyPlanConfig(coverage_portfolio=False)."""
        if not getattr(self.cfg, "coverage_portfolio", True):
            return self._build_once(day, source_file)
        if self._is_distance_objective():
            return self._build_portfolio(day, source_file)
        plan = self._build_once(day, source_file)
        if self._recoverable_drops(plan):
            return self._build_portfolio(day, source_file, seed=plan)
        return plan

    def _recoverable_drops(self, plan: dict[str, Any]) -> int:
        """Count unassigned drops that a different makespan MIGHT recover — i.e.
        serviceable deliveries the solver merely failed to fit (not the hard
        export/ungeocodable/oversize ones)."""
        n = 0
        for u in plan.get("unassigned", []):
            reason = str(u.get("unassigned_reason") or "").lower()
            if not any(marker in reason for marker in self._HARD_DROP_MARKERS):
                n += 1
        return n

    def _secondary_metric(self, plan: dict[str, Any]) -> float:
        """The metric minimised AMONG equally-covering plans, per objective:
        green/cost → CO₂; fast → day finish time; balanced/other → TND cost."""
        obj = str(self.cfg.objective or "balanced").lower()
        if obj in ("green", "cost"):
            return float(plan.get("estimated_co2_kg") or 0.0)
        if obj == "fast":
            return float(self._plan_finish_minutes(plan))
        return float((plan.get("estimated_cost_tnd") or {}).get("total") or 0.0)

    @staticmethod
    def _plan_finish_minutes(plan: dict[str, Any]) -> int:
        """Latest truck return across the plan, in minutes (0 if idle)."""
        latest = 0
        for t in plan.get("trucks", []):
            for trip in t.get("trips", []):
                try:
                    hh, mm = str(trip.get("return_at")).split(":")[:2]
                    latest = max(latest, int(hh) * 60 + int(mm))
                except (ValueError, AttributeError):
                    continue
        return latest

    def _build_portfolio(
        self, day: date, source_file: Optional[str] = None, seed: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Solve a portfolio of makespan settings and keep the plan that serves
        the MOST customers (coverage is lexicographically first), then the best
        objective-appropriate secondary metric. `seed` (an already-built plan) is
        included as a candidate so the portfolio never returns a worse result than
        the natural solve. Per-solve time is capped so the extra solves stay cheap."""
        label = str(self.cfg.objective or "balanced").lower()
        candidates: list[dict[str, Any]] = []
        if seed is not None:
            candidates.append(seed)

        prev_seconds = self.cfg.global_solver_seconds
        self.cfg.global_solver_seconds = min(prev_seconds, 4)  # cap per-solve cost
        try:
            for coef in self._PORTFOLIO_COEFS:
                self._makespan_override = coef
                try:
                    candidates.append(self._build_once(day, source_file))
                finally:
                    self._makespan_override = None
        finally:
            self.cfg.global_solver_seconds = prev_seconds

        # Maximise coverage (fewest unassigned), then minimise the secondary.
        best = min(
            candidates,
            key=lambda p: (len(p.get("unassigned", [])), self._secondary_metric(p)),
        )
        # Present it under the requested objective label, whichever coef won.
        best["objective"] = label
        if isinstance(best.get("sustainability"), dict):
            best["sustainability"]["objective"] = label
        return best

    def _build_once(self, day: date, source_file: Optional[str] = None) -> dict[str, Any]:
        source_path = self._resolve_source_file(source_file)
        plan_data = PlanningService(db=None).parse_weekly_planning(str(source_path))
        rows, selection = self._filter_rows(plan_data["rows"], day)
        delivery_rows = [row for row in rows if row.get("client")]
        deliveries = [self._delivery_from_row(row, day) for row in delivery_rows]
        # Mark URGENT drops from their comment so the urgent rules can fire.
        for d in deliveries:
            if "urgent" in str((d.get("raw") or {}).get("notes") or "").lower():
                d["priority"] = "urgent"

        depot = self.geo.depot()

        # Splitting is a DECISION VARIABLE, not preprocessing. Generate demand
        # variants but do not mutate the input: solve the unsplit baseline AND a
        # split-enabled variant fully and independently, score the FINAL plans
        # (with a penalty per split so it is never "free"), and keep the cheapest.
        # The unsplit baseline is always in the running, so enabling splits can
        # never degrade the operational plan.
        base_variant = list(deliveries)
        split_variant = [sub for d in deliveries for sub in self._maybe_split(d)]
        variants: list[tuple[str, list, float]] = [("baseline", base_variant, 0.0)]
        split_parents = {d["_split_parent"] for d in split_variant if d.get("_split_parent") is not None}
        if split_parents:
            extra_stops = max(0, len(split_variant) - len(base_variant))
            split_penalty = (
                self._W_SPLIT_CUSTOMER * len(split_parents) + self._W_SPLIT_STOP * extra_stops
            )
            variants.append(("split", split_variant, split_penalty))

        solved = []
        for vname, vdeliveries, vpenalty in variants:
            v_trucks, v_unassigned, v_routable, v_cost = self._evaluate(vdeliveries, depot)
            solved.append((v_cost + vpenalty, vname, v_trucks, v_unassigned, v_routable))
        total_cost, variant_name, trucks, unassigned, routable = min(solved, key=lambda s: s[0])
        log.info(
            "DailyPlanBuilder: variant '%s' won (cost=%.0f) among %s",
            variant_name, total_cost, {s[1]: round(s[0]) for s in solved},
        )

        clean_trucks = [self._clean_truck(t) for t in trucks]
        estimated_cost_tnd = self._cost_breakdown(trucks, unassigned)
        sustainability = self._sustainability(trucks, unassigned, routable, depot)
        rental_recommendations = self._rental_recommendations(unassigned)

        return {
            "plan_id": str(uuid.uuid4()),
            "day": day.isoformat(),
            "source_file": source_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": (
                "global multi-vehicle VRPTW (OR-Tools: capacity+kg+time dimensions, "
                "multi-trip, drop penalties) over split/baseline demand variants"
                if HAS_ORTOOLS else
                "cluster-first heuristic portfolio over split/baseline demand variants"
            ),
            "depot": {"lat": depot[0], "lon": depot[1]},
            "work_window": {"start": self.cfg.work_start, "end": self.cfg.work_end},
            "selection": selection,
            "variant": variant_name,
            "summary": {
                "source_rows": len(plan_data["rows"]),
                "selected_rows": len(rows),
                "selected_delivery_rows": len(delivery_rows),
                "deliveries_considered": len(deliveries),
                "deliveries_routed": len(routable),
                "total_positions": int(sum(self._pos(d) for d in routable)),
                "total_gross_weight_kg": round(sum(self._kg(d) for d in routable), 2),
                "total_volume_m3": round(sum(self._vol(d) for d in routable), 1),
            },
            "objective": str(self.cfg.objective or "balanced").lower(),
            "trucks": clean_trucks,
            "unassigned": [self._clean_stop(d) for d in unassigned],
            "rental_recommendations": rental_recommendations,
            "estimated_cost_tnd": estimated_cost_tnd,
            "estimated_co2_kg": sustainability["co2_kg"],
            "sustainability": sustainability,
            "diagnostics": self._diagnostics(trucks, unassigned, routable, self.truck_templates),
        }

    # ------------------------------------------------------------- replanning
    def replan(self, day: date, deliveries: list[dict[str, Any]]) -> dict[str, Any]:
        """Re-optimise an EXPLICIT set of deliveries on this builder's fleet,
        without touching the workbook or re-splitting. Used for self-healing
        recovery: feed the still-undelivered stops and a (possibly reduced) fleet
        and get a fresh plan in the same shape as build(). The caller diffs it
        against the original plan to show what changed.
        """
        depot = self.geo.depot()
        # Work on copies so _evaluate's in-place tagging never mutates the input.
        items = [dict(d) for d in deliveries]
        for d in items:
            d.setdefault("constraints", {})
            d.setdefault("priority", "normal")
        trucks, unassigned, routable, total_cost = self._evaluate(items, depot)
        clean_trucks = [self._clean_truck(t) for t in trucks]
        sustainability = self._sustainability(trucks, unassigned, routable, depot)
        return {
            "plan_id": str(uuid.uuid4()),
            "day": day.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "replanned": True,
            "algorithm": (
                "self-healing residual VRPTW (OR-Tools) over the undelivered stops"
                if HAS_ORTOOLS else
                "self-healing residual cluster-first heuristic over the undelivered stops"
            ),
            "depot": {"lat": depot[0], "lon": depot[1]},
            "work_window": {"start": self.cfg.work_start, "end": self.cfg.work_end},
            "objective": str(self.cfg.objective or "balanced").lower(),
            "summary": {
                "deliveries_considered": len(items),
                "deliveries_routed": len(routable),
                "total_positions": int(sum(self._pos(d) for d in routable)),
                "total_gross_weight_kg": round(sum(self._kg(d) for d in routable), 2),
                "total_volume_m3": round(sum(self._vol(d) for d in routable), 1),
            },
            "trucks": clean_trucks,
            "unassigned": [self._clean_stop(d) for d in unassigned],
            "estimated_cost_tnd": self._cost_breakdown(trucks, unassigned),
            "estimated_co2_kg": sustainability["co2_kg"],
            "sustainability": sustainability,
            "diagnostics": self._diagnostics(trucks, unassigned, routable, self.truck_templates),
        }

    def _evaluate(self, deliveries, depot):
        """Solve one demand variant end-to-end: resolve → feasibility filter →
        cost-scored fleet candidates → schedule. Returns
        (trucks, unassigned, routable, final_cost). The unsplit/oversize and
        unlocatable drops are all included in the final cost, so variants are
        compared on their true delivered service, not just the routed part."""
        unassigned: list[dict[str, Any]] = []
        routable: list[dict[str, Any]] = []

        # Resolve every customer (client directory first, then geocode).
        for delivery in deliveries:
            loc = self.geo.locate(delivery.get("geocode_as") or delivery["client"])
            if loc is None:
                unassigned.append({**delivery, "unassigned_reason": f"Could not locate “{delivery['client']}”"})
                continue
            if loc.get("is_export"):
                unassigned.append({**delivery, "unassigned_reason": "Export / foreign site — not a domestic truck run"})
                continue
            delivery["lat"], delivery["lon"] = loc["lat"], loc["lon"]
            delivery["resolved_location"] = loc["label"]
            delivery["_table_km"] = loc.get("km")
            routable.append(delivery)

        trucks = [self._fresh_truck(t) for t in self.truck_templates]

        # Hard capacity: a drop larger than the biggest truck cannot load at all.
        max_truck_cap = max((t["capacity_positions"] for t in trucks), default=-1)
        max_truck_kg = max((t["capacity_kg"] for t in trucks), default=-1)
        vol_on = self._volume_enforced(trucks)
        max_truck_m3 = max((float(t.get("capacity_m3") or 0) for t in trucks), default=-1.0)
        servable: list[dict[str, Any]] = []
        for d in routable:
            qty_pos = self._pos(d)
            qty_kg = self._kg(d)
            qty_m3 = self._vol(d)
            if not trucks:
                unassigned.append({**self._clean_stop(d), "unassigned_reason": "No available trucks"})
            elif qty_pos > max_truck_cap:
                unassigned.append({**self._clean_stop(d), "unassigned_reason": (
                    f"{int(qty_pos)} positions exceeds the largest truck "
                    f"({max_truck_cap}) — needs a delivery split")})
            elif qty_kg > max_truck_kg:
                unassigned.append({**self._clean_stop(d), "unassigned_reason": (
                    f"{int(qty_kg)} kg exceeds the largest truck "
                    f"({int(max_truck_kg)} kg) — needs a delivery split")})
            elif vol_on and qty_m3 > max_truck_m3 + 1e-6:
                unassigned.append({**self._clean_stop(d), "unassigned_reason": (
                    f"{qty_m3:.1f} m³ exceeds the largest truck "
                    f"({max_truck_m3:.0f} m³) — the load cubes out; needs a delivery split")})
            else:
                servable.append(d)

        if servable:
            dur_min = self._build_matrix(servable, depot)
            for i, d in enumerate(servable):
                d["_mi"] = i + 1

            # Primary: solve the WHOLE fleet as one global VRPTW (joint
            # assignment + routing + time). Fall back to the cluster-first
            # heuristic portfolio if OR-Tools is unavailable/disabled or the
            # global solve fails to return.
            global_solved = (
                self._solve_global_vrptw(servable, dur_min)
                if (HAS_ORTOOLS and self.cfg.prefer_ortools) else None
            )
            if global_solved is not None:
                trucks, g_unassigned = global_solved
                unassigned.extend(g_unassigned)
            else:
                candidates = []
                for name, assign_fn in (
                    ("zones", self._assign_to_trucks),
                    ("packed", self._assign_insertion),
                ):
                    ct, cu = self._run_strategy(servable, dur_min, assign_fn)
                    candidates.append((self._plan_cost(ct, cu), name, ct, cu))
                _, _, trucks, best_unassigned = min(candidates, key=lambda c: c[0])
                unassigned.extend(best_unassigned)

        return trucks, unassigned, routable, self._plan_cost(trucks, unassigned)

    # ----------------------------------------------------- global VRPTW solver
    def _solve_global_vrptw(self, servable, dur):
        """Solve the full multi-vehicle VRPTW in a single OR-Tools model:

          • one node per delivery (node 0 = depot), every vehicle depot-rooted;
          • two capacity dimensions — positions AND real gross kg — per vehicle;
          • a time dimension with travel + service transit, customer time windows
            (Excel), depart-by-cut-off start bounds and evening returns allowed;
          • multi-trip: each truck is replicated into ``trips_per_truck`` vehicle
            slots whose start times are chained (a truck runs its trips in
            sequence, with a reload gap between them);
          • optional drops via disjunctions, with urgent loads near-mandatory;
          • an escalating fixed cost per dispatched trip plus a global makespan
            term, so the day finishes early by running well-filled trucks in
            parallel rather than a few trucks doing many sequential trips (the
            rented truck stays heavily penalised as a last resort).

        Returns (trucks_with_trips, unassigned) or None on failure.
        """
        try:
            templates = self.truck_templates
            n = len(servable)
            if not n:
                return None
            early = self._minutes(self.cfg.early_start)
            cutoff = self._minutes(self.cfg.max_depart)
            work_start = self._minutes(self.cfg.work_start)
            horizon = 24 * 60
            reload = self.cfg.reload_minutes

            # Replicate each physical truck into N trip-slots (separate
            # vehicles). veh_trip records the 0-based trip index of each slot so
            # later trips on the same truck can be priced higher than a fresh
            # truck's first trip.
            veh_truck: list[int] = []
            veh_trip: list[int] = []
            for ti in range(len(templates)):
                for k in range(max(1, self.cfg.trips_per_truck)):
                    veh_truck.append(ti)
                    veh_trip.append(k)
            V = len(veh_truck)
            if V == 0:
                return None
            cap_pos = [int(templates[veh_truck[v]]["capacity_positions"]) for v in range(V)]
            cap_kg = [int(templates[veh_truck[v]]["capacity_kg"]) for v in range(V)]
            # Volume is a third capacity dimension. Demands/capacities are scaled
            # by 10 and rounded to integers (OR-Tools dimensions are integer) so
            # one decimal of m³ precision is preserved. Only enabled when the
            # fleet declares capacity_m3 for every truck.
            vol_on = self._volume_enforced(templates)
            cap_m3 = [
                int(round(float(templates[veh_truck[v]].get("capacity_m3") or 0) * 10))
                for v in range(V)
            ]

            manager = pywrapcp.RoutingIndexManager(n + 1, V, 0)
            routing = pywrapcp.RoutingModel(manager)

            def transit(from_idx, to_idx):
                i = manager.IndexToNode(from_idx)
                j = manager.IndexToNode(to_idx)
                service = 0 if i == 0 else self._service_minutes(servable[i - 1])
                return int(round(dur[i][j])) + service
            tcb = routing.RegisterTransitCallback(transit)

            # The cost the solver MINIMISES is pure travel distance (time),
            # EXCLUDING on-site service time. Service time belongs in the Time
            # dimension (scheduling), not in the objective — folding it in
            # penalises the solver per stop served, which pulls the objective away
            # from true distance/CO₂ minimisation. Time still uses `tcb`
            # (travel+service) below so arrival times stay correct. (W2.1)
            def travel_only(from_idx, to_idx):
                i = manager.IndexToNode(from_idx)
                j = manager.IndexToNode(to_idx)
                return int(round(dur[i][j]))
            dcb = routing.RegisterTransitCallback(travel_only)
            routing.SetArcCostEvaluatorOfAllVehicles(dcb)

            # Fixed cost per dispatched trip, escalating with the trip index:
            # a truck's first trip costs ``trip_dispatch_cost`` (the soft "fill
            # the truck before opening another" pressure), and every subsequent
            # trip on the SAME truck adds ``extra_trip_cost`` — so the solver
            # prefers dispatching a fresh truck (cheap first trip, runs in
            # parallel) over piling a 2nd/3rd trip onto one truck. The hired
            # truck is a genuine last resort (a real rental bill), so it keeps a
            # heavy surcharge on top.
            for v in range(V):
                fixed = self.cfg.trip_dispatch_cost + veh_trip[v] * self.cfg.extra_trip_cost
                if self._is_rental(templates[veh_truck[v]]):
                    fixed += 20000
                routing.SetFixedCostOfVehicle(fixed, v)

            # Capacity dimensions — positions and real gross weight.
            def pos_dem(from_idx):
                i = manager.IndexToNode(from_idx)
                return 0 if i == 0 else int(round(self._pos(servable[i - 1])))
            routing.AddDimensionWithVehicleCapacity(
                routing.RegisterUnaryTransitCallback(pos_dem), 0, cap_pos, True, "Positions")

            def kg_dem(from_idx):
                i = manager.IndexToNode(from_idx)
                return 0 if i == 0 else int(round(self._kg(servable[i - 1])))
            routing.AddDimensionWithVehicleCapacity(
                routing.RegisterUnaryTransitCallback(kg_dem), 0, cap_kg, True, "Kg")

            if vol_on:
                def vol_dem(from_idx):
                    i = manager.IndexToNode(from_idx)
                    return 0 if i == 0 else int(round(self._vol(servable[i - 1]) * 10))
                routing.AddDimensionWithVehicleCapacity(
                    routing.RegisterUnaryTransitCallback(vol_dem), 0, cap_m3, True, "Volume")

            # Time dimension (slack lets a truck wait for a window to open).
            routing.AddDimension(tcb, horizon, horizon, False, "Time")
            time_dim = routing.GetDimensionOrDie("Time")
            time_dim.SetSpanCostCoefficientForAllVehicles(1)  # trim idle/waiting
            # Global makespan/balance term: penalise (latest return − earliest
            # departure) across the whole fleet, so the solver spreads load onto
            # trucks running in parallel and the LAST truck gets home sooner,
            # rather than queuing many trips on a few trucks. The coefficient is
            # selected by the objective mode (green/balanced/fast) so the same
            # model can be re-solved at different points on the cost↔time frontier.
            time_dim.SetGlobalSpanCostCoefficient(self._makespan_coef())
            for v in range(V):
                time_dim.CumulVar(routing.Start(v)).SetRange(early, cutoff)
            for i in range(1, n + 1):
                window = servable[i - 1]["constraints"].get("time_window")
                lo, hi = (
                    (self._minutes(window[0]), self._minutes(window[1]))
                    if window else (work_start, horizon)
                )
                time_dim.CumulVar(manager.NodeToIndex(i)).SetRange(lo, hi)

            # Multi-trip: a truck's slots run sequentially with a reload gap.
            solver = routing.solver()
            slots: dict[int, list[int]] = {}
            for v in range(V):
                slots.setdefault(veh_truck[v], []).append(v)
            for vs in slots.values():
                for a, b in zip(vs, vs[1:]):
                    solver.Add(
                        time_dim.CumulVar(routing.Start(b))
                        >= time_dim.CumulVar(routing.End(a)) + reload
                    )

            # Allow drops, but make them very expensive (urgent ~ mandatory).
            for i in range(1, n + 1):
                penalty = 100_000_000 if self._is_urgent(servable[i - 1]) else 1_000_000
                routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

            params = pywrapcp.DefaultRoutingSearchParameters()
            params.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            params.time_limit.FromSeconds(max(1, int(self.cfg.global_solver_seconds)))
            sol = routing.SolveWithParameters(params)
            if sol is None:
                return None

            trucks = [self._fresh_truck(t) for t in templates]
            assigned_nodes: set[int] = set()
            for v in range(V):
                start = routing.Start(v)
                if routing.IsEnd(sol.Value(routing.NextVar(start))):
                    continue  # unused slot
                truck = trucks[veh_truck[v]]
                stops: list[dict[str, Any]] = []
                idx = start
                prev_node = 0
                depart = sol.Value(time_dim.CumulVar(start))
                while not routing.IsEnd(idx):
                    node = manager.IndexToNode(idx)
                    if node != 0:
                        d = servable[node - 1]
                        arrival = sol.Value(time_dim.CumulVar(idx))
                        service = self._service_minutes(d)
                        stops.append({
                            **self._clean_stop(d),
                            "etd": self._clock(int(round(arrival))),
                            "eta": self._clock(int(round(arrival + service))),
                            "travel_min": int(round(dur[prev_node][node])),
                            "service_min": int(round(service)),
                        })
                        assigned_nodes.add(node)
                        prev_node = node
                    idx = sol.Value(routing.NextVar(idx))
                return_at = sol.Value(time_dim.CumulVar(idx))
                truck.setdefault("_pending", []).append((depart, return_at, stops))

            for truck in trucks:
                pending = truck.pop("_pending", [])
                pending.sort(key=lambda x: x[0])
                for k, (depart, return_at, stops) in enumerate(pending, start=1):
                    truck["trips"].append({
                        "trip_id": f"{truck['truck_id']}-{k}",
                        "depart_at": self._clock(int(round(depart))),
                        "return_at": self._clock(int(round(return_at))),
                        "stops": stops,
                    })

            unassigned = [
                {**self._clean_stop(servable[i - 1]),
                 "unassigned_reason": "No feasible vehicle/time slot in the working day"}
                for i in range(1, n + 1) if i not in assigned_nodes
            ]
            log.info(
                "Global VRPTW: %d/%d delivered, %d trips on %d trucks",
                len(assigned_nodes), n,
                sum(len(t["trips"]) for t in trucks),
                sum(1 for t in trucks if t["trips"]),
            )
            return trucks, unassigned
        except Exception as exc:  # never break the planner — fall back
            log.warning("Global VRPTW failed, using heuristic fallback — %s", exc)
            return None

    # --------------------------------------------------- global fleet packing
    # Business objective (iteration 1): minimise total transport waste, not just
    # blindly hit 80%. We try several global assignment strategies, schedule
    # each, and score with a weighted cost; a truck may depart under 80% only if
    # no cheaper consolidation exists.
    UTIL_TARGET = 0.80          # a truck "should" depart at least this full
    MAX_DETOUR_KM = 130.0       # max straight-line pull to consolidate a drop

    # Operational cost weights live in CostConfig (TND); the plan objective is
    # computed in _cost_breakdown(). Service coverage stays lexicographically
    # above everything else via CostConfig.unassigned_delivery_penalty_tnd,
    # which is an order of magnitude larger than any operational term.
    #
    # Splitting is a structural trade-off, never free — these TND overheads keep
    # the optimiser from splitting unless it genuinely lowers the total cost
    # (e.g. avoids the hired truck or an unassigned drop). Scaled to the same
    # TND objective as the operational costs above.
    _W_SPLIT_CUSTOMER = 8.0     # TND overhead per customer that gets split
    _W_SPLIT_STOP = 4.0         # TND overhead per extra stop a split creates
    # Split comments are EXACT business quantities: warn on any mismatch beyond
    # this tolerance (0 = flag every discrepancy) instead of silently rescaling.
    SPLIT_QTY_TOLERANCE = 0

    @staticmethod
    def _is_urgent(d: dict[str, Any]) -> bool:
        return str(d.get("priority") or "").strip().lower() == "urgent"

    def _feasible_trucks(self, d, trucks):
        """Trucks that can legally carry this drop by positions, kg AND volume.

        The volume test only applies where the fleet declares ``capacity_m3``
        (and volume enforcement is on), so an ad-hoc truck set without volumes
        keeps the original positions+kg behaviour unchanged."""
        dp, dk = self._pos(d), self._kg(d)
        dv = self._vol(d)
        return [
            t for t in trucks
            if t["capacity_positions"] >= dp and t["capacity_kg"] >= dk
            and self._fits_volume(t, dv)
        ]

    def _volume_enforced(self, trucks: list[dict[str, Any]]) -> bool:
        """Volume binds only when enforcement is on AND every truck in the set
        declares a positive capacity_m3 — otherwise a missing capacity would
        wrongly forbid all load, so we leave the dimension off for that fleet."""
        return bool(
            getattr(self.cfg, "enforce_volume", True)
            and trucks
            and all(float(t.get("capacity_m3") or 0) > 0 for t in trucks)
        )

    def _fits_volume(self, truck: dict[str, Any], volume_m3: float) -> bool:
        cap = float(truck.get("capacity_m3") or 0)
        if not getattr(self.cfg, "enforce_volume", True) or cap <= 0:
            return True  # this truck doesn't constrain volume
        return cap + 1e-6 >= volume_m3

    @staticmethod
    def _pos(d: dict[str, Any]) -> float:
        return float(d.get("quantity_positions") or d.get("position_count") or 0)

    @staticmethod
    def _kg(d: dict[str, Any]) -> float:
        return float(d.get("quantity_kg") or 0)

    def _vol(self, d: dict[str, Any]) -> float:
        """A delivery's cargo volume in m³: its explicit ``volume_m3`` when set,
        otherwise derived from positions × the configured per-position deck
        volume. Always non-negative; never invents volume for a 0-position drop."""
        explicit = d.get("volume_m3")
        if explicit is not None:
            try:
                v = float(explicit)
                if v >= 0:
                    return v
            except (TypeError, ValueError):
                pass
        return self._pos(d) * float(getattr(self.cfg, "m3_per_position", 1.8) or 0.0)

    def _run_strategy(self, servable, dur_min, assign_fn):
        """Assign with `assign_fn`, then schedule + rescue on a fresh fleet."""
        trucks = [self._fresh_truck(t) for t in self.truck_templates]
        groups = assign_fn(servable, trucks)
        overflow_all: list[dict[str, Any]] = []
        for truck in trucks:
            items = groups.get(truck["truck_id"], [])
            if items:
                overflow_all.extend(self._schedule_truck(truck, items, dur_min))
        unassigned: list[dict[str, Any]] = []
        for d in self._rescue_overflow(trucks, overflow_all):
            reason = d.get("unassigned_reason") or "Exceeds working hours"
            unassigned.append({**self._clean_stop(d), "unassigned_reason": reason})
        return trucks, unassigned

    def _plan_cost(self, trucks, unassigned) -> float:
        """Operational cost of a plan in TND (lower is better). The solver
        minimises this; the same breakdown is reported as estimated_cost_tnd."""
        return self._cost_breakdown(trucks, unassigned)["total"]

    def _cost_breakdown(self, trucks, unassigned) -> dict[str, float]:
        """Plan cost decomposed into real TND terms (fuel, driver, trucks,
        under-utilisation, unassigned penalty), derived from self.cost_config.

        The unassigned penalty (>= 2000 TND/drop) stays an order of magnitude
        above any operational term, preserving the lexicographic rule that a
        plan serving all customers always beats one that drops a delivery.
        """
        cfg = self.cost_config
        used = [t for t in trucks if t.get("trips")]
        total_travel_min = 0.0
        empty_positions = 0.0
        cost_trucks = 0.0
        for t in used:
            cap_p = float(t["capacity_positions"]) or 1.0
            is_rented = self._is_rental(t)
            cost_trucks += cfg.rental_truck_per_day_tnd if is_rented else cfg.truck_dispatch_fixed_tnd
            for trip in t["trips"]:
                stops = trip.get("stops", [])
                if not stops:
                    continue
                pos = sum(self._pos(s) for s in stops)
                empty_positions += max(0.0, cap_p - pos)
                total_travel_min += sum(float(s.get("travel_min") or 0) for s in stops)

        total_km = total_travel_min / 60.0 * self.cfg.avg_speed_kmh
        total_hours = total_travel_min / 60.0
        cost_fuel = total_km * cfg.fuel_price_tnd_per_liter * cfg.fuel_consumption_l_per_100km / 100.0
        cost_driver = total_hours * cfg.driver_hourly_cost_tnd
        cost_underutil = empty_positions * cfg.underutil_penalty_per_pos
        cost_unassigned = sum(
            cfg.unassigned_delivery_penalty_tnd
            * (cfg.urgent_unassigned_multiplier if self._is_urgent(u) else 1.0)
            for u in unassigned
        )
        total = cost_trucks + cost_fuel + cost_driver + cost_underutil + cost_unassigned
        return {
            "total": round(total, 2),
            "trucks": round(cost_trucks, 2),
            "fuel": round(cost_fuel, 2),
            "driver": round(cost_driver, 2),
            "underutilization": round(cost_underutil, 2),
            "unassigned_penalty": round(cost_unassigned, 2),
        }

    # ------------------------------------------------------ objective / ESG
    # Makespan-coefficient presets per objective mode. Higher = the solver works
    # harder to finish the day early (more parallel trucks, more km); 0 = pure
    # distance/CO₂ minimisation (fewest, fullest trucks, day may finish later).
    _MAKESPAN_PRESETS = {"green": 0, "cost": 0, "balanced": None, "fast": 12}

    def _makespan_coef(self) -> int:
        # A green-portfolio solve overrides the makespan coefficient directly.
        override = getattr(self, "_makespan_override", None)
        if override is not None:
            return max(0, int(override))
        preset = self._MAKESPAN_PRESETS.get(str(self.cfg.objective or "balanced").lower(), None)
        coef = self.cfg.makespan_cost_coef if preset is None else preset
        return max(0, int(coef))

    def _is_distance_objective(self) -> bool:
        """green/cost = minimise driven distance & CO₂ (the environmental point on
        the frontier), as opposed to balanced/fast which trade distance for an
        earlier finish. These objectives use the coverage-first CO₂ portfolio in
        ``build`` rather than a single fixed-makespan solve."""
        return str(self.cfg.objective or "balanced").lower() in ("green", "cost")

    def _plan_travel_km(self, trucks) -> float:
        """Total driven kilometres across every dispatched trip in a plan.

        Derived from each stop's travel_min and the configured average speed, so
        it stays on the same model as the schedule and the TND cost breakdown."""
        travel_min = sum(
            float(s.get("travel_min") or 0)
            for t in trucks if t.get("trips")
            for trip in t["trips"]
            for s in trip.get("stops", [])
        )
        return travel_min / 60.0 * self.cfg.avg_speed_kmh

    def _co2_kg(self, km: float) -> float:
        liters = km * self.cost_config.fuel_consumption_l_per_100km / 100.0
        return liters * self.cost_config.co2_kg_per_liter_diesel

    def _baseline_km(self, routable, depot) -> float:
        """Unoptimised 'before' distance: every delivery served by its own direct
        depot→client→depot round trip (no consolidation, no shared routes). This
        is the honest manual baseline the optimiser is measured against."""
        total = 0.0
        for d in routable:
            one_way = d.get("distance_km")
            if one_way is None:
                one_way = d.get("_table_km")
            if one_way is None and d.get("lat") is not None:
                one_way = _haversine_km(depot[0], depot[1], d["lat"], d["lon"]) * ROAD_WINDING_FACTOR
            total += 2.0 * float(one_way or 0.0)
        return total

    def _sustainability(self, trucks, unassigned, routable, depot) -> dict[str, Any]:
        """Carbon & ESG summary for a plan: fuel, CO₂, the distance/CO₂ saved
        versus the unconsolidated manual baseline, and intuitive equivalences."""
        planned_km = self._plan_travel_km(trucks)
        fuel_l = planned_km * self.cost_config.fuel_consumption_l_per_100km / 100.0
        co2_kg = self._co2_kg(planned_km)

        baseline_km = self._baseline_km(routable, depot)
        baseline_co2 = self._co2_kg(baseline_km)
        co2_saved = max(0.0, baseline_co2 - co2_kg)
        km_saved = max(0.0, baseline_km - planned_km)
        saved_pct = round(100.0 * co2_saved / baseline_co2, 1) if baseline_co2 > 0 else 0.0

        delivered_pos = sum(
            self._pos(s)
            for t in trucks if t.get("trips")
            for trip in t["trips"]
            for s in trip.get("stops", [])
        )
        co2_per_pos = round(co2_kg / delivered_pos, 2) if delivered_pos else None

        return {
            "objective": str(self.cfg.objective or "balanced").lower(),
            "planned_distance_km": round(planned_km, 1),
            "baseline_distance_km": round(baseline_km, 1),
            "distance_saved_km": round(km_saved, 1),
            "fuel_liters": round(fuel_l, 1),
            "co2_kg": round(co2_kg, 1),
            "baseline_co2_kg": round(baseline_co2, 1),
            "co2_saved_kg": round(co2_saved, 1),
            "co2_saved_pct": saved_pct,
            "co2_kg_per_position": co2_per_pos,
            "co2_kg_per_liter": self.cost_config.co2_kg_per_liter_diesel,
            # Friendly equivalences for the ESG card: a mature tree absorbs
            # ~21 kg CO₂/yr; an average car emits ~0.12 kg CO₂/km.
            "trees_year_equivalent": round(co2_saved / 21.0, 1),
            "car_km_equivalent": round(co2_saved / 0.12, 0),
        }

    def _assign_insertion(self, servable, trucks):
        """Global packing: place each drop (largest first) on the nearest truck
        already working within an acceptable detour that can carry it; otherwise
        open the smallest adequate idle truck. Multi-trip is left to the
        scheduler, so big drops needing the 24-pallet truck can still share it."""
        by_id = {t["truck_id"]: t for t in trucks}
        groups: dict[int, list[dict[str, Any]]] = {t["truck_id"]: [] for t in trucks}
        free: list[dict[str, Any]] = []
        for d in servable:
            req = d["constraints"].get("required_truck_id")
            if req and req in by_id:
                groups[req].append(d)
            else:
                free.append(d)
        used = {tid for tid, ds in groups.items() if ds}

        # Priority order: lock the most-constrained drops first (few feasible
        # trucks), then urgent, then biggest — so a delivery that fits only one
        # truck claims it before packing spends it on something flexible.
        def _order_key(d):
            return (
                len(self._feasible_trucks(d, trucks)) or 99,
                0 if self._is_urgent(d) else PRIORITY_WEIGHT.get(
                    str(d.get("priority") or "normal").lower(), 2
                ),
                -self._pos(d),
                -self._kg(d),
            )

        for d in sorted(free, key=_order_key):
            dp, dk = self._pos(d), self._kg(d)
            fits = self._feasible_trucks(d, trucks) or list(trucks)

            # 1) nearest already-working truck within detour that can carry it
            chosen, best_near = None, None
            for t in fits:
                g = groups[t["truck_id"]]
                if not g:
                    continue
                c_lat = sum(x["lat"] for x in g) / len(g)
                c_lon = sum(x["lon"] for x in g) / len(g)
                near = _haversine_km(c_lat, c_lon, d["lat"], d["lon"])
                if near <= self.MAX_DETOUR_KM and (best_near is None or near < best_near):
                    chosen, best_near = t, near

            # 2) else open the smallest adequate idle truck (right-size)
            if chosen is None:
                idle = sorted(
                    (t for t in fits if t["truck_id"] not in used),
                    key=lambda t: (t["capacity_positions"], t["capacity_kg"]),
                )
                chosen = idle[0] if idle else min(
                    fits, key=lambda t: (t["capacity_positions"], t["capacity_kg"])
                )

            groups[chosen["truck_id"]].append(d)
            used.add(chosen["truck_id"])
        return groups

    def _diagnostics(self, trucks, unassigned, considered, fleet):
        """Operator visibility: urgent assignments, fleet bottlenecks, under-full
        departures, and the exact constraint behind every unassigned drop."""
        assigned_to: dict[str, str] = {}
        for t in trucks:
            for trip in t.get("trips", []):
                for s in trip.get("stops", []):
                    assigned_to[str(s.get("client"))] = t["truck_label"]

        urgent = [
            {"client": d.get("client"), "truck": assigned_to.get(str(d.get("client")), "UNASSIGNED")}
            for d in considered if self._is_urgent(d)
        ]
        single, two_or_fewer = [], []
        for d in considered:
            feas = self._feasible_trucks(d, fleet)
            if len(feas) == 1:
                single.append({
                    "client": d.get("client"), "only_truck": feas[0]["truck_label"],
                    "positions": self._pos(d), "kg": self._kg(d),
                })
            if len(feas) <= 2:
                two_or_fewer.append({
                    "client": d.get("client"),
                    "feasible_trucks": [t["truck_label"] for t in feas],
                })

        vol_on = getattr(self.cfg, "enforce_volume", True)
        under = []
        for t in trucks:
            cap_p = float(t["capacity_positions"]) or 1.0
            cap_k = float(t["capacity_kg"]) or 1.0
            cap_v = float(t.get("capacity_m3") or 0)
            for trip in t.get("trips", []):
                stops = trip.get("stops", [])
                if not stops:
                    continue
                pos = sum(self._pos(s) for s in stops)
                kg = sum(self._kg(s) for s in stops)
                vol = sum(self._vol(s) for s in stops)
                # The binding dimension is whichever fills the truck most. Volume
                # counts only when the truck declares a capacity, so a load that
                # cubes out (full m³, light kg) is correctly seen as full.
                util = max(pos / cap_p, kg / cap_k)
                if vol_on and cap_v > 0:
                    util = max(util, vol / cap_v)
                if util < self.UTIL_TARGET:
                    under.append({
                        "truck": t["truck_label"], "trip": trip.get("trip_id"),
                        "utilization_pct": round(util * 100),
                        "reason": "no remaining compatible drop fit within capacity and the consolidation detour limit",
                    })

        unassigned_diag = [
            {"client": u.get("client"), "positions": self._pos(u), "kg": self._kg(u),
             "urgent": self._is_urgent(u), "constraint": u.get("unassigned_reason")}
            for u in unassigned
        ]
        return {
            "urgent_deliveries": urgent,
            "single_feasible_truck": single,
            "two_or_fewer_feasible_trucks": two_or_fewer,
            "under_80pct_departures": under,
            "unassigned": unassigned_diag,
            "hos_warnings": self._hos_warnings(trucks),
        }

    # Tunisian driving regulation limits (informational only — the plan is still
    # returned; the dispatcher is responsible for legal compliance).
    HOS_DRIVING_LIMIT_MIN = 540   # 9 h max daily driving
    HOS_ON_DUTY_LIMIT_MIN = 780   # 13 h max daily on-duty (first depart→last return)

    def _hos_warnings(self, trucks) -> list[dict[str, Any]]:
        """Flag trucks whose day exceeds the driving (9 h) or on-duty (13 h)
        limits. Warning only: overruns are surfaced, never silently dropped."""
        def _clock_min(value) -> Optional[int]:
            # depart_at/return_at are _clock() strings and may exceed 24:00
            # (late returns), which _minutes() rejects — parse HH:MM directly.
            try:
                hh, mm = str(value).split(":")[:2]
                return int(hh) * 60 + int(mm)
            except (ValueError, AttributeError):
                return None

        warnings: list[dict[str, Any]] = []
        for t in trucks:
            trips = t.get("trips") or []
            if not trips:
                continue
            driving = int(round(sum(
                float(s.get("travel_min") or 0)
                for trip in trips for s in trip.get("stops", [])
            )))
            departs = [m for trip in trips if (m := _clock_min(trip.get("depart_at"))) is not None]
            returns = [m for trip in trips if (m := _clock_min(trip.get("return_at"))) is not None]
            on_duty = int(max(returns) - min(departs)) if departs and returns else 0
            if driving > self.HOS_DRIVING_LIMIT_MIN or on_duty > self.HOS_ON_DUTY_LIMIT_MIN:
                warnings.append({
                    "truck": t.get("truck_label"),
                    "driver": t.get("driver"),
                    "driving_minutes": driving,
                    "on_duty_minutes": on_duty,
                    "driving_limit": self.HOS_DRIVING_LIMIT_MIN,
                    "on_duty_limit": self.HOS_ON_DUTY_LIMIT_MIN,
                    "driving_overflow_minutes": max(0, driving - self.HOS_DRIVING_LIMIT_MIN),
                    "on_duty_overflow_minutes": max(0, on_duty - self.HOS_ON_DUTY_LIMIT_MIN),
                })
        return warnings

    # --------------------------------------------------------- delivery splits
    def _maybe_split(self, delivery: dict[str, Any]) -> list[dict[str, Any]]:
        """Split a multi-site drop described in its comment into one sub-delivery
        per site, e.g. "24pos beja1 8pos beja 2" -> 24-pos Béja-1 + 8-pos Béja-2.
        Each piece keeps the client identity but routes to its own city so the
        pieces can ride different trucks. Returns [delivery] when nothing splits."""
        raw = delivery.get("raw") or {}
        comment = raw.get("notes") or raw.get("comment") or delivery.get("commentaire") or ""
        parts = self._parse_split_comment(comment)
        if not parts:
            return [delivery]

        base_kg = float(delivery.get("quantity_kg") or 0)
        base_vol = float(delivery.get("volume_m3") or 0)
        base_id = delivery.get("id") or 0
        original_client = delivery.get("client") or ""
        orig_pos = int(round(float(delivery.get("quantity_positions") or 0)))
        site_labels = [label for _, label in parts]
        explicit = [int(p) for p, _ in parts]

        # QUANTITY CONSERVATION (critical): the parts must sum to EXACTLY the
        # original positions — a split must never lose or create positions.
        # Honour the comment's split but let the last part absorb the remainder
        # (33 -> 24 + 9, never 24 + 8). If the comment's numbers exceed the
        # original, scale them down proportionally.
        sizes = explicit[:]
        if orig_pos > 0:
            sizes[-1] = orig_pos - sum(explicit[:-1])
            if sizes[-1] <= 0:
                total = sum(explicit) or 1
                sizes = [max(1, round(orig_pos * p / total)) for p in explicit]
                sizes[-1] = orig_pos - sum(sizes[:-1])
            if sum(sizes) != orig_pos:  # safeguard against rounding drift
                sizes[-1] += orig_pos - sum(sizes)
        total_pos = sum(sizes) or 1
        max_cap = int(max((t["capacity_positions"] for t in self.truck_templates), default=0))

        # Split comments are treated as EXACT business quantities. If the comment
        # total does not match the delivery total (beyond a small tolerance) we
        # still conserve positions, but raise a warning so a workbook typo is
        # surfaced to the planner instead of being silently absorbed.
        comment_total = sum(explicit)
        discrepancy = orig_pos - comment_total
        split_warning = None
        if orig_pos > 0 and abs(discrepancy) > self.SPLIT_QTY_TOLERANCE:
            split_warning = (
                f"Quantity mismatch: the split comment totals {comment_total} positions but the "
                f"delivery has {orig_pos}. Please check the source workbook — the "
                f"{abs(discrepancy)}-position difference was applied to {site_labels[-1].title()} "
                f"to keep the total correct."
            )
            log.warning(
                "DailyPlanBuilder: split of '%s' quantity mismatch (comment=%s, delivery=%s)",
                original_client, comment_total, orig_pos,
            )

        # Friendly, planner-facing explanation listing each resulting drop.
        resulting = [f"{sizes[i]} positions ({site_labels[i].title()})" for i in range(len(sizes))]
        resulting_phrase = (
            resulting[0] if len(resulting) == 1
            else ", ".join(resulting[:-1]) + " and " + resulting[-1]
        )
        explanation = (
            f"Delivery automatically split because {orig_pos} positions exceed the maximum "
            f"truck capacity of {max_cap} positions. Resulting deliveries: {resulting_phrase}."
        )
        if split_warning:
            explanation = f"{explanation} ⚠ {split_warning}"

        subs: list[dict[str, Any]] = []
        for i, label in enumerate(site_labels, start=1):
            pos = sizes[i - 1]
            city = self._split_city(label) or original_client
            subs.append({
                **delivery,
                "id": (int(base_id) * 100 + i) if str(base_id).isdigit() else f"{base_id}-{i}",
                "client": f"{original_client} ({label.title()})" if label else original_client,
                "original_client": original_client,
                "split_label": label.title() if label else None,
                "geocode_as": city,
                "quantity_positions": float(pos),
                "position_count": float(pos),
                "quantity_kg": round(base_kg * pos / total_pos, 1),
                "volume_m3": round(base_vol * pos / total_pos, 3),
                "_split_parent": base_id,
                # --- Explainability / traceability of the automatic split ---
                "is_split": True,
                "split_reason": "CAPACITY_OVERFLOW",
                "split_parent_id": base_id,
                "split_part": i,
                "split_total_parts": len(site_labels),
                "split_positions": int(pos),
                "planning_comment": explanation,
                "split_warning": split_warning,
            })

        # Safeguard: never lose or create positions in a split.
        produced = sum(s["split_positions"] for s in subs)
        if orig_pos > 0 and produced != orig_pos:
            log.error("Split of '%s' broke quantity conservation: %s != %s",
                      original_client, produced, orig_pos)
        log.info("DailyPlanBuilder: split '%s' (%s pos) -> %s", original_client, orig_pos, sizes)
        return subs

    @staticmethod
    def _parse_split_comment(comment: Any) -> Optional[list[tuple[int, str]]]:
        """Parse "24pos beja1 8pos beja 2" -> [(24, 'beja1'), (8, 'beja 2')]."""
        text = str(comment or "").strip().lower()
        if "pos" not in text:
            return None
        toks = re.split(r"(\d+)\s*pos\b", text)
        parts: list[tuple[int, str]] = []
        i = 1
        while i < len(toks):
            try:
                n = int(toks[i])
            except (TypeError, ValueError):
                i += 1
                continue
            label = toks[i + 1].strip() if i + 1 < len(toks) else ""
            if n > 0:
                parts.append((n, label))
            i += 2
        return parts if len(parts) >= 2 else None

    @staticmethod
    def _split_city(label: str) -> str:
        """'beja1' / 'beja 2' -> 'Beja' (strip the trailing site number)."""
        return re.sub(r"[\s\d]+$", "", str(label or "")).strip().title()

    # ------------------------------------------------------------ travel time
    def _build_matrix(
        self, routable: list[dict[str, Any]], depot: tuple[float, float]
    ) -> list[list[float]]:
        """Travel-time matrix (minutes), node 0 = depot.

        Preferred path: real driving distances from OSRM for every leg (depot↔
        client and client↔client). Fallback (OSRM unreachable): the directory's
        real road km for depot legs and straight-line × a road-winding factor
        for the rest. Either way every leg's time is distance ÷ average truck
        speed, so the displayed km and the scheduled time stay on one model."""
        speed = self.cfg.avg_speed_kmh
        n = len(routable)
        size = n + 1
        dur = [[0.0] * size for _ in range(size)]

        # --- preferred: real road distances from OSRM ---------------------
        if self.cfg.use_osrm_road_matrix:
            coords = [depot] + [(d["lat"], d["lon"]) for d in routable]
            road = None
            if self.osrm is not None:
                try:
                    table = self.osrm.table(coords)
                    road = [[float(meters) / 1000.0 for meters in row] for row in table.distances_m]
                except Exception:
                    road = None
            if road is None:
                road = self.geo.road_km_matrix(coords)
            if road is not None:
                for i, d in enumerate(routable):
                    d["distance_km"] = round(road[0][i + 1], 1)  # depot → client
                for a in range(size):
                    for b in range(size):
                        if a != b:
                            dur[a][b] = road[a][b] / speed * 60.0
                return dur

        # --- fallback: directory km (depot) + haversine × winding ---------
        depot_km: list[float] = []
        for d in routable:
            table_km = d.get("_table_km")
            km = (
                float(table_km) if table_km is not None
                else _haversine_km(depot[0], depot[1], d["lat"], d["lon"]) * ROAD_WINDING_FACTOR
            )
            depot_km.append(km)
            d["distance_km"] = round(km, 1)

        for i in range(n):
            t = depot_km[i] / speed * 60.0
            dur[0][i + 1] = dur[i + 1][0] = t
        for i in range(n):
            for j in range(i + 1, n):
                km = _haversine_km(
                    routable[i]["lat"], routable[i]["lon"],
                    routable[j]["lat"], routable[j]["lon"],
                ) * ROAD_WINDING_FACTOR
                t = km / speed * 60.0
                dur[i + 1][j + 1] = dur[j + 1][i + 1] = t
        return dur

    # -------------------------------------------------------- truck assignment
    def _assign_to_trucks(
        self, routable: list[dict[str, Any]], trucks: list[dict[str, Any]]
    ) -> dict[int, list[dict[str, Any]]]:
        """Split deliveries across trucks: pinned ones honoured, the rest
        partitioned into compact geographic zones — one zone per truck.

        Zones are kept geographically pure (a truck never borrows a stop from
        another region just to balance load). Within-zone overload is absorbed
        by multiple trips, scheduled later, not by mixing distant stops.
        """
        by_id = {t["truck_id"]: t for t in trucks}
        groups: dict[int, list[dict[str, Any]]] = {t["truck_id"]: [] for t in trucks}

        free: list[dict[str, Any]] = []
        for d in routable:
            req = d["constraints"].get("required_truck_id")
            if req and req in by_id:
                groups[req].append(d)  # honour the Excel-pinned vehicle
            else:
                free.append(d)

        if not free:
            return groups

        # Reserve trucks that already carry a pinned load less aggressively:
        # cluster across all trucks, then prefer empty trucks for new zones.
        latlons = [(d["lat"], d["lon"]) for d in free]
        k = min(len(trucks), len(free))
        raw = [zone for zone in cluster_zones(latlons, k=k) if zone]

        # Largest (heaviest) zone goes to the largest-capacity truck so a big
        # region needs the fewest trips. Any dispatcher-approved rental is kept
        # as a last resort, so owned capacity is exhausted first.
        trucks_sorted = sorted(
            trucks,
            key=lambda t: (
                len(groups[t["truck_id"]]) > 0,
                self._is_rental(t),
                -t["capacity_positions"],
            ),
        )

        def zone_demand(zone: list[dict[str, Any]]) -> tuple[float, float, float]:
            pos = [float(d.get("quantity_positions") or 0) for d in zone]
            kg = [float(d.get("quantity_kg") or 0) for d in zone]
            # Hardest single drop first (positions, then kg — it dictates the
            # truck size needed), then total positions as a tie-breaker.
            return (max(pos, default=0.0), max(kg, default=0.0), sum(pos))

        zones_by_demand = sorted(
            ([free[i] for i in zone] for zone in raw),
            key=zone_demand,
            reverse=True,
        )

        # Capacity-feasibility-aware assignment: take zones biggest-demand first
        # and give each the best still-free truck that can physically carry its
        # hardest single drop by BOTH positions and weight, so a heavy or bulky
        # drop never lands on a truck that cannot legally haul it.
        available = list(trucks_sorted)
        for zone in zones_by_demand:
            if not available:
                break
            max_pos = max((float(d.get("quantity_positions") or 0) for d in zone), default=0.0)
            max_kg = max((float(d.get("quantity_kg") or 0) for d in zone), default=0.0)
            max_m3 = max((self._vol(d) for d in zone), default=0.0)
            choice = next(
                (t for t in available
                 if t["capacity_positions"] >= max_pos and t["capacity_kg"] >= max_kg
                 and self._fits_volume(t, max_m3)),
                None,
            )
            if choice is None:
                # No remaining truck fits the hardest drop; fall back to the
                # roomiest one so the scheduler reports the true overflow.
                choice = max(available, key=lambda t: (t["capacity_kg"], t["capacity_positions"]))
            groups[choice["truck_id"]].extend(zone)
            available.remove(choice)
        return groups

    # ------------------------------------------------------------- scheduling
    # A forced wait longer than this means it is cheaper (and more realistic)
    # for the truck to drive back to the depot and run a second trip later.
    LONG_WAIT_SPLIT_MIN = 120

    def _schedule_truck(
        self, truck: dict[str, Any], items: list[dict[str, Any]], dur_min: list[list[float]]
    ) -> list[dict[str, Any]]:
        """Order the truck's stops, then walk them into depot-rooted trips,
        opening a new trip when capacity is full or a time window forces a long
        wait. Returns the deliveries that did not fit the working day."""
        order = self._order_stops(items, dur_min)
        capacity = truck["capacity_positions"]
        cap_kg = float(truck["capacity_kg"])
        cap_m3 = float(truck.get("capacity_m3") or 0)
        vol_on = self._volume_enforced([truck])
        max_depart = self._minutes(self.cfg.max_depart)
        work_start = self._minutes(self.cfg.work_start)
        early_start = self._minutes(self.cfg.early_start)

        # The truck can be staged from the early-start hour; a regular (short)
        # first trip is still floored at normal opening below, but a long haul is
        # allowed to roll out at first light.
        cursor = early_start  # truck free-at-depot time
        overflow: list[dict[str, Any]] = []

        trip_stops: list[dict[str, Any]] = []
        depart_at = float(cursor)
        load = 0.0       # positions on the open trip
        load_kg = 0.0    # gross weight on the open trip
        load_m3 = 0.0    # cargo volume on the open trip
        t = float(cursor)
        prev = 0  # depot node

        def close_trip() -> None:
            nonlocal cursor, trip_stops, load, load_kg, load_m3, prev, t, depart_at
            if not trip_stops:
                return
            # The trip already passed the depart-by-max_depart gate when it left
            # the depot, so it is committed regardless of how late it returns —
            # far zones are served by driving the empty truck home in the evening.
            return_at = t + dur_min[prev][0]
            truck["trips"].append({
                "trip_id": f"{truck['truck_id']}-{len(truck['trips']) + 1}",
                "depart_at": self._clock(int(round(depart_at))),
                "return_at": self._clock(int(round(return_at))),
                "stops": list(trip_stops),
            })
            cursor = return_at + self.cfg.reload_minutes
            trip_stops = []
            load = 0.0
            load_kg = 0.0
            load_m3 = 0.0
            prev = 0
            t = float(cursor)
            depart_at = float(cursor)

        for d in order:
            mi = d["_mi"]
            qty = float(d.get("quantity_positions") or 0)
            qty_kg = float(d.get("quantity_kg") or 0)
            qty_m3 = self._vol(d)
            if qty > capacity or qty_kg > cap_kg or (vol_on and qty_m3 > cap_m3 + 1e-6):
                # Servable in principle (it fits a bigger truck), but every
                # larger truck is already committed to a heavier zone today.
                if qty > capacity:
                    limit = f"{capacity} positions"
                elif qty_kg > cap_kg:
                    limit = f"{int(cap_kg)} kg"
                else:
                    limit = f"{cap_m3:.0f} m³"
                overflow.append({
                    **d,
                    "unassigned_reason": (
                        f"{qty:.0f} pos / {qty_kg:.0f} kg / {qty_m3:.1f} m³ exceeds this "
                        f"truck's {limit} — all larger trucks are committed today"
                    ),
                })
                continue
            window = d["constraints"].get("time_window")
            win_start = self._minutes(window[0]) if window else None
            win_end = self._minutes(window[1]) if window else None

            # Tentative arrival if we append to the current (open) trip.
            in_trip = bool(trip_stops)
            arrival = t + dur_min[prev][mi]
            forced_wait = max(0, (win_start - arrival)) if win_start is not None else 0

            if in_trip and (
                load + qty > capacity
                or load_kg + qty_kg > cap_kg
                or (vol_on and load_m3 + qty_m3 > cap_m3 + 1e-6)
                or forced_wait > self.LONG_WAIT_SPLIT_MIN
            ):
                close_trip()
                in_trip = False

            if not in_trip:
                # Leaving the depot fresh: depart late enough to roll straight
                # into the window instead of idling at the customer.
                leg = dur_min[0][mi]
                # Long hauls may leave at first light (05:00); regular trips are
                # floored at normal opening (06:00) so we don't run short routes
                # uselessly early.
                is_long_haul = float(d.get("distance_km") or 0) >= self.cfg.long_haul_km
                floor = early_start if is_long_haul else work_start
                start = max(cursor, floor)
                if win_start is not None:
                    start = max(floor, win_start - int(round(leg)))
                # A truck may not LEAVE the depot after the daily cut-off, even
                # though it is allowed to return in the evening.
                if start > max_depart:
                    overflow.append({
                        **d,
                        "unassigned_reason": (
                            f"Truck cannot depart by {self.cfg.max_depart} for this stop"
                        ),
                    })
                    continue
                depart_at = start
                t = float(start)
                prev = 0
                arrival = t + leg

            if win_start is not None and arrival < win_start:
                arrival = float(win_start)
            service = self._service_minutes(d)
            service_end = arrival + service

            if win_end is not None and arrival > win_end:
                overflow.append({**d, "unassigned_reason": "Outside customer time window"})
                continue

            trip_stops.append({
                **self._clean_stop(d),
                "etd": self._clock(int(round(arrival))),
                "eta": self._clock(int(round(service_end))),
                "travel_min": int(round(dur_min[prev][mi])),
                "service_min": int(round(service)),
            })
            t = service_end
            prev = mi
            load += qty
            load_kg += qty_kg
            load_m3 += qty_m3

        close_trip()
        return overflow

    def _rescue_overflow(
        self, trucks: list[dict[str, Any]], overflow: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Try to place each overflowed delivery on a truck with spare time.

        Builds one extra depot→drop→depot trip per rescued delivery, starting
        when the chosen truck next becomes free at the depot. A truck is only
        used if it can carry the drop by BOTH positions and weight and finish the
        round trip before the working day ends (and inside any time window).
        Heaviest drops are placed first so they claim the few high-capacity
        trucks; the smallest adequate, owned truck is preferred so big and hired
        vehicles stay free for loads that truly need them. Returns the deliveries
        that still could not be placed."""
        work_start = self._minutes(self.cfg.work_start)
        early_start = self._minutes(self.cfg.early_start)
        max_depart = self._minutes(self.cfg.max_depart)
        speed = self.cfg.avg_speed_kmh

        def free_at(truck: dict[str, Any], floor: int) -> int:
            if truck["trips"]:
                return self._minutes(truck["trips"][-1]["return_at"]) + self.cfg.reload_minutes
            return floor

        still: list[dict[str, Any]] = []
        ordered = sorted(
            overflow,
            key=lambda d: (float(d.get("quantity_kg") or 0), float(d.get("quantity_positions") or 0)),
            reverse=True,
        )
        for d in ordered:
            qty = float(d.get("quantity_positions") or 0)
            qty_kg = float(d.get("quantity_kg") or 0)
            qty_m3 = self._vol(d)
            km = d.get("distance_km")
            if km is None:
                still.append(d)
                continue
            leg = float(km) / speed * 60.0
            service = self._service_minutes(d)
            # A long-haul rescue may stage an idle truck from first light (05:00)
            # so its evening return is as early as possible.
            floor = early_start if float(km) >= self.cfg.long_haul_km else work_start
            window = d.get("constraints", {}).get("time_window")
            win_start = self._minutes(window[0]) if window else None
            win_end = self._minutes(window[1]) if window else None

            candidates = [
                t for t in trucks
                if t["capacity_positions"] >= qty and float(t["capacity_kg"]) >= qty_kg
                and self._fits_volume(t, qty_m3)
            ]
            # Owned before hired, smallest adequate first, then earliest free.
            candidates.sort(key=lambda t: (
                self._is_rental(t),
                t["capacity_positions"],
                free_at(t, floor),
            ))

            placed = False
            for t in candidates:
                start = free_at(t, floor)
                if win_start is not None:
                    start = max(floor, win_start - int(round(leg)))
                # Depart-by-cut-off is the binding rule; the evening return home
                # may run past the work window.
                if start > max_depart:
                    continue
                arrival = start + leg
                if win_start is not None and arrival < win_start:
                    arrival = float(win_start)
                service_end = arrival + service
                return_at = service_end + leg
                if win_end is not None and arrival > win_end:
                    continue
                t["trips"].append({
                    "trip_id": f"{t['truck_id']}-{len(t['trips']) + 1}",
                    "depart_at": self._clock(int(round(start))),
                    "return_at": self._clock(int(round(return_at))),
                    "stops": [{
                        **self._clean_stop(d),
                        "etd": self._clock(int(round(arrival))),
                        "eta": self._clock(int(round(service_end))),
                        "travel_min": int(round(leg)),
                        "service_min": int(round(service)),
                    }],
                })
                placed = True
                break
            if not placed:
                still.append(d)
        return still

    def _service_minutes(self, delivery: dict[str, Any]) -> int:
        positions = float(delivery.get("quantity_positions") or delivery.get("position_count") or 0)
        computed = self.cfg.service_minutes + positions * self.cfg.service_minutes_per_position
        return int(round(min(self.cfg.max_service_minutes, max(self.cfg.service_minutes, computed))))

    def _order_stops(
        self, items: list[dict[str, Any]], dur_min: list[list[float]]
    ) -> list[dict[str, Any]]:
        """Return items in an efficient visiting order (depot-rooted)."""
        if len(items) <= 1:
            return list(items)
        local = [0] + [d["_mi"] for d in items]
        if HAS_ORTOOLS and self.cfg.prefer_ortools:
            order_idx = self._ortools_vrptw_order(local, items, dur_min)
            if order_idx is not None:
                return [items[i] for i in order_idx]
            order_idx = self._ortools_tsp(local, dur_min)
            if order_idx is not None:
                return [items[i] for i in order_idx]
        return self._greedy_order(items, dur_min)

    def _ortools_vrptw_order(
        self,
        local: list[int],
        items: list[dict[str, Any]],
        dur_min: list[list[float]],
    ) -> Optional[list[int]]:
        """Single-truck VRPTW ordering: distance objective with time windows.

        Assignment to trucks happens before this method. This solver chooses a
        feasible order for one truck's zone, respecting delivery time windows
        where the workbook provides them. The scheduler below still emits the
        final human-readable arrival/departure times sequentially.
        """
        try:
            n = len(local)
            manager = pywrapcp.RoutingIndexManager(n, 1, 0)
            routing = pywrapcp.RoutingModel(manager)

            def distance_cost(from_idx: int, to_idx: int) -> int:
                gi = local[manager.IndexToNode(from_idx)]
                gj = local[manager.IndexToNode(to_idx)]
                return int(dur_min[gi][gj] * 100)

            def transit_time(from_idx: int, to_idx: int) -> int:
                from_node = manager.IndexToNode(from_idx)
                gi = local[from_node]
                gj = local[manager.IndexToNode(to_idx)]
                service = 0 if gi == 0 else self._service_minutes(items[from_node - 1])
                return int(round(dur_min[gi][gj] + service))

            cost_cb = routing.RegisterTransitCallback(distance_cost)
            routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)
            time_cb = routing.RegisterTransitCallback(transit_time)
            # Returns from far zones may run into the evening, so the time
            # horizon extends past work_end; the binding rule is that the truck
            # leaves the depot no later than max_depart.
            early_start = self._minutes(self.cfg.early_start)
            max_depart = self._minutes(self.cfg.max_depart)
            late_horizon = 24 * 60
            routing.AddDimension(time_cb, late_horizon, late_horizon, False, "Time")
            time_dim = routing.GetDimensionOrDie("Time")
            time_dim.CumulVar(routing.Start(0)).SetRange(early_start, max_depart)
            time_dim.CumulVar(routing.End(0)).SetRange(early_start, late_horizon)

            for local_pos, delivery in enumerate(items, start=1):
                index = manager.NodeToIndex(local_pos)
                window = delivery["constraints"].get("time_window")
                if window:
                    start = self._minutes(window[0])
                    end = self._minutes(window[1])
                else:
                    start = early_start
                    end = late_horizon
                time_dim.CumulVar(index).SetRange(start, end)

            params = pywrapcp.DefaultRoutingSearchParameters()
            params.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            # Zones hold ≤ a couple dozen stops; guided local search converges in
            # well under a second, so a short cap keeps the planner responsive.
            params.time_limit.FromMilliseconds(300)
            solution = routing.SolveWithParameters(params)
            if solution is None:
                return None

            order: list[int] = []
            idx = routing.Start(0)
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                if node != 0:
                    order.append(node - 1)
                idx = solution.Value(routing.NextVar(idx))
            return order
        except Exception as exc:
            log.warning("DailyPlanBuilder: OR-Tools VRPTW ordering failed — %s", exc)
            return None

    def _ortools_tsp(
        self, local: list[int], dur_min: list[list[float]]
    ) -> Optional[list[int]]:
        try:
            n = len(local)
            manager = pywrapcp.RoutingIndexManager(n, 1, 0)
            routing = pywrapcp.RoutingModel(manager)

            def cost(from_idx: int, to_idx: int) -> int:
                gi = local[manager.IndexToNode(from_idx)]
                gj = local[manager.IndexToNode(to_idx)]
                return int(dur_min[gi][gj] * 100)

            cb = routing.RegisterTransitCallback(cost)
            routing.SetArcCostEvaluatorOfAllVehicles(cb)
            params = pywrapcp.DefaultRoutingSearchParameters()
            params.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            params.time_limit.FromMilliseconds(200)
            solution = routing.SolveWithParameters(params)
            if solution is None:
                return None
            order: list[int] = []
            idx = routing.Start(0)
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                if node != 0:
                    order.append(node - 1)  # back to items[] position
                idx = solution.Value(routing.NextVar(idx))
            return order
        except Exception as exc:
            log.warning("DailyPlanBuilder: OR-Tools ordering failed — %s", exc)
            return None

    @staticmethod
    def _greedy_order(
        items: list[dict[str, Any]], dur_min: list[list[float]]
    ) -> list[dict[str, Any]]:
        remaining = list(items)
        ordered: list[dict[str, Any]] = []
        cur = 0
        while remaining:
            nxt = min(remaining, key=lambda d: dur_min[cur][d["_mi"]])
            ordered.append(nxt)
            cur = nxt["_mi"]
            remaining.remove(nxt)
        return ordered

    # --------------------------------------------------------------- cleaners
    @staticmethod
    def _fresh_truck(truck: dict[str, Any]) -> dict[str, Any]:
        return {**truck, "trips": []}

    @staticmethod
    def _is_rental(truck: dict[str, Any]) -> bool:
        return truck.get("ownership") == "RENTAL" or bool(truck.get("rental_profile"))

    @staticmethod
    def _clean_truck(truck: dict[str, Any]) -> dict[str, Any]:
        clean = {
            "truck_id": truck["truck_id"],
            "truck_label": truck["truck_label"],
            "capacity_positions": truck["capacity_positions"],
            "capacity_kg": truck["capacity_kg"],
            "ownership": truck.get("ownership", "OWNED"),
            "rental_profile": truck.get("rental_profile"),
            "rental_approval_id": truck.get("rental_approval_id"),
            "estimated_cost_eur": truck.get("estimated_cost_eur"),
            "trips": truck["trips"],
        }
        if truck.get("capacity_m3") is not None:
            clean["capacity_m3"] = truck["capacity_m3"]
        return clean

    @staticmethod
    def _rental_recommendations(unassigned: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Propose, but never auto-approve, the smallest viable rental class."""
        grouped: dict[str, dict[str, Any]] = {}
        for delivery in unassigned:
            reason = str(delivery.get("unassigned_reason") or "")
            if "Could not locate" in reason or "Export / foreign" in reason:
                continue
            positions = float(
                delivery.get("quantity_positions")
                or delivery.get("position_count")
                or 0
            )
            weight = float(delivery.get("quantity_kg") or 0)
            profile = next(
                (
                    item for item in RENTAL_PROFILES
                    if item["capacity_positions"] >= positions
                    and item["capacity_kg"] >= weight
                ),
                None,
            )
            if profile is None:
                continue
            key = profile["profile"]
            recommendation = grouped.setdefault(
                key,
                {
                    "id": f"rental-{key.lower()}",
                    **profile,
                    "approval_required": True,
                    "status": "PROPOSED",
                    "feasibility_status": "REQUIRES_REOPTIMIZATION",
                    "delivery_ids": [],
                    "reasons": [],
                    "estimated_cost_eur": float(profile["fixed_cost_eur"]),
                    "truck": {
                        "truck_id": 9001 + RENTAL_PROFILES.index(profile),
                        "truck_label": f"Rental · {profile['vehicle_type']}",
                        "capacity_positions": profile["capacity_positions"],
                        "capacity_kg": profile["capacity_kg"],
                        "ownership": "RENTAL",
                        "rental_profile": key,
                    },
                },
            )
            recommendation["delivery_ids"].append(delivery.get("id"))
            if reason and reason not in recommendation["reasons"]:
                recommendation["reasons"].append(reason)
            one_way_km = float(
                delivery.get("depot_distance_km")
                or delivery.get("distance_km")
                or 0
            )
            recommendation["estimated_cost_eur"] += (
                one_way_km * 2 * float(profile["cost_per_km_eur"])
            )

        for recommendation in grouped.values():
            recommendation["estimated_cost_eur"] = round(
                recommendation["estimated_cost_eur"], 2
            )
            recommendation["truck"]["estimated_cost_eur"] = recommendation[
                "estimated_cost_eur"
            ]
        return list(grouped.values())

    @staticmethod
    def _clean_stop(delivery: dict[str, Any]) -> dict[str, Any]:
        keep = (
            "id", "client", "start_location", "end_location", "quantity_positions",
            "position_count", "quantity_kg", "volume_m3", "etd", "eta", "priority", "status",
            "constraints", "raw", "lat", "lon", "distance_km", "resolved_location",
            "travel_min", "unassigned_reason",
            # Split explainability / traceability:
            "is_split", "split_reason", "split_parent_id", "split_part",
            "split_total_parts", "split_positions", "planning_comment",
            "original_client", "split_label", "split_warning",
        )
        return {k: delivery[k] for k in keep if k in delivery}

    # ------------------------------------------------------------- parsing IO
    def _resolve_source_file(self, source_file: Optional[str]) -> Path:
        if source_file:
            path = (self.source_dir / source_file).resolve()
            if self.source_dir.resolve() not in path.parents and path != self.source_dir.resolve():
                raise ValueError("source_file must stay inside weekly planning")
            if not path.exists():
                raise FileNotFoundError(f"source file not found: {source_file}")
            return path

        files = sorted(
            self.source_dir.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        files = [p for p in files if not p.name.startswith("~$")]
        if not files:
            raise FileNotFoundError("no weekly planning xlsx file found")
        return files[0]

    def _filter_rows(self, rows: list[dict[str, Any]], target_day: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        target_name = target_day.strftime("%A")
        matched = [
            row for row in rows
            if (row.get("delivery_date") and row["delivery_date"].date() == target_day)
            or row.get("delivery_day") == target_name
        ]
        if matched:
            return matched, {
                "requested_date": target_day.isoformat(),
                "requested_day": target_name,
                "matched_day": target_name,
                "fallback": False,
            }
        fallback_day = next((row.get("delivery_day") for row in rows if row.get("delivery_day")), None)
        fallback_rows = [row for row in rows if row.get("delivery_day") == fallback_day] if fallback_day else rows
        return fallback_rows, {
            "requested_date": target_day.isoformat(),
            "requested_day": target_name,
            "matched_day": fallback_day,
            "fallback": True,
        }

    def _delivery_from_row(self, row: dict[str, Any], target_day: date) -> dict[str, Any]:
        constraints = PlanningService.parse_constraints(row)
        etd = self._format_time(row.get("etd"))
        eta = self._format_time(row.get("eta"))
        if constraints.get("time_window"):
            etd, eta = constraints["time_window"]
        positions = float(row.get("position_count") or row.get("quantity") or 0)
        # Stress-test scaling: probe "+X% volume" scenarios without touching the
        # workbook. 1.0 is a no-op (the normal path).
        mult = float(getattr(self.cfg, "demand_multiplier", 1.0) or 1.0)
        if mult != 1.0:
            positions = round(positions * mult, 2)
        # Cargo volume: explicit m³ from the workbook if present, else derived
        # from positions × the per-position deck volume. Scaled with the same
        # stress-test multiplier as positions/kg so a "+X% volume" scenario also
        # inflates the m³ load.
        explicit_vol = self._volume_from_row(row)
        volume_m3 = (
            explicit_vol if explicit_vol is not None
            else positions * float(getattr(self.cfg, "m3_per_position", 1.8) or 0.0)
        )
        if explicit_vol is not None and mult != 1.0:
            volume_m3 = explicit_vol * mult
        return {
            "id": int(row.get("row_number") or 0),
            "client": row.get("client") or row.get("end_location") or "Unknown client",
            "start_location": row.get("start_location") or "COFICAB Sidi Hassine",
            "end_location": row.get("end_location") or row.get("client") or "Unknown destination",
            "quantity_positions": positions,
            "position_count": positions,
            # Capacity binds on BOTH positions and the real gross weight declared
            # in the workbook (rows without a weight contribute 0 kg, so weight
            # only constrains where the data exists — it never invents a limit).
            "quantity_kg": round(self._weight_from_row(row) * mult, 2),
            "volume_m3": round(volume_m3, 3),
            "etd": etd,
            "eta": eta,
            "priority": row.get("priority") or "normal",
            "status": "planned",
            "constraints": {
                **constraints,
                "required_date": constraints.get("required_date") or target_day.isoformat(),
            },
            "raw": row,
        }

    @staticmethod
    def _weight_from_row(row: dict[str, Any]) -> float:
        for key in ("total_gross_weight_kg", "gross_weight_kg", "pallet_weight_kg"):
            value = row.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _volume_from_row(row: dict[str, Any]) -> Optional[float]:
        """Explicit cargo volume in m³ from the workbook, if any column carries
        it. Returns None when no volume is declared so the caller derives it
        from positions instead of inventing a limit."""
        for key in ("total_volume_m3", "volume_m3", "volume_cbm", "cbm", "m3"):
            value = row.get(key)
            if value is None:
                continue
            try:
                v = float(value)
                if v >= 0:
                    return v
            except (TypeError, ValueError):
                continue
        return None

    # --------------------------------------------------------------- time util
    @staticmethod
    def _format_time(value: Any) -> Optional[str]:
        minutes = DailyPlanBuilder._minutes(value)
        return DailyPlanBuilder._clock(minutes) if minutes is not None else None

    @staticmethod
    def _minutes(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.hour * 60 + value.minute
        if isinstance(value, time):
            return value.hour * 60 + value.minute
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.hour * 60 + parsed.minute
            except ValueError:
                pass
        # Late-return clocks may intentionally exceed 24:00 (for example
        # 25:14), which datetime.strptime rejects.
        try:
            hours, minutes = text.split(":")[:2]
            if int(hours) >= 0 and 0 <= int(minutes) < 60:
                return int(hours) * 60 + int(minutes)
        except (ValueError, TypeError):
            pass
        try:
            numeric = int(float(text))
            if 0 <= numeric < 24:
                return numeric * 60
            if 0 <= numeric < 2400:
                return (numeric // 100) * 60 + numeric % 100
        except ValueError:
            return None
        return None

    @staticmethod
    def _clock(minutes: int) -> str:
        """Format a minutes-since-midnight value as HH:MM.

        Late returns (>= 24:00) are NOT clamped to 23:59 — they keep counting
        (e.g. 1514 -> "25:14") so the dispatcher sees the real elapsed time
        instead of a silently wrong value. A warning is logged so ops notice
        a plan that overruns midnight. The Gantt's toMinutes() parses hours
        beyond 24 correctly and clamps only the visual bar position.
        """
        minutes = max(0, int(minutes))
        if minutes >= 24 * 60:
            log.warning(
                "DailyPlanBuilder._clock: trip time %d min exceeds midnight -> %02d:%02d",
                minutes, minutes // 60, minutes % 60,
            )
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
