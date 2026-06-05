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
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from app.services.geo_service import GeoService, _haversine_km, ROAD_WINDING_FACTOR
from app.services.planning_service import PlanningService
from app.services.vrptw_optimizer import cluster_zones

log = logging.getLogger(__name__)


DEFAULT_TRUCKS = [
    {"truck_id": 1, "truck_label": "Truck 1", "capacity_positions": 14, "capacity_kg": 10_200},
    {"truck_id": 2, "truck_label": "Truck 2", "capacity_positions": 14, "capacity_kg": 10_230},
    {"truck_id": 3, "truck_label": "Truck 3", "capacity_positions": 14, "capacity_kg": 9_227},
    {"truck_id": 4, "truck_label": "Truck 4", "capacity_positions": 14, "capacity_kg": 9_200},
    {"truck_id": 5, "truck_label": "Truck 5", "capacity_positions": 24, "capacity_kg": 24_950},
    {"truck_id": 6, "truck_label": "Truck 6", "capacity_positions": 14, "capacity_kg": 7_650},
    {"truck_id": 999, "truck_label": "Rented", "capacity_positions": 24, "capacity_kg": 24_000},
]

PRIORITY_WEIGHT = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False


@dataclass
class DailyPlanConfig:
    work_start: str = "06:00"      # depots open early for long hauls
    work_end: str = "20:00"
    service_minutes: int = 20      # minimum on-site setup/(un)loading time
    service_minutes_per_position: float = 3.0
    max_service_minutes: int = 120
    reload_minutes: int = 30       # back at depot between trips of one truck
    avg_speed_kmh: float = 55.0    # loaded-truck average over Tunisian roads


class DailyPlanBuilder:
    def __init__(
        self,
        source_dir: Path,
        cfg: Optional[DailyPlanConfig] = None,
        geo: Optional[GeoService] = None,
        trucks: Optional[list[dict[str, Any]]] = None,
    ):
        self.source_dir = source_dir
        self.cfg = cfg or DailyPlanConfig()
        self.geo = geo or GeoService()
        self.truck_templates = trucks or DEFAULT_TRUCKS

    # ------------------------------------------------------------------ build
    def build(self, day: date, source_file: Optional[str] = None) -> dict[str, Any]:
        source_path = self._resolve_source_file(source_file)
        plan_data = PlanningService(db=None).parse_weekly_planning(str(source_path))
        rows, selection = self._filter_rows(plan_data["rows"], day)
        delivery_rows = [row for row in rows if row.get("client")]
        deliveries = [self._delivery_from_row(row, day) for row in delivery_rows]

        depot = self.geo.depot()
        unassigned: list[dict[str, Any]] = []
        routable: list[dict[str, Any]] = []

        # Step 2: resolve every customer (client directory first, then geocode).
        for delivery in deliveries:
            loc = self.geo.locate(delivery["client"])
            if loc is None:
                unassigned.append({**delivery, "unassigned_reason": f"Could not locate “{delivery['client']}”"})
                continue
            if loc.get("is_export"):
                unassigned.append({**delivery, "unassigned_reason": "Export / foreign site — not a domestic truck run"})
                continue
            delivery["lat"], delivery["lon"] = loc["lat"], loc["lon"]
            delivery["resolved_location"] = loc["label"]
            delivery["_table_km"] = loc.get("km")  # authoritative depot distance
            routable.append(delivery)

        trucks = [self._fresh_truck(t) for t in self.truck_templates]

        # A single delivery larger than the biggest truck can never be loaded —
        # set these aside up front so they don't consume a large truck that a
        # servable delivery needs (a 33-pos drop must not steal the 24-truck a
        # 16-pos drop could use).
        max_truck_cap = max(t["capacity_positions"] for t in trucks)
        max_truck_kg = max(t["capacity_kg"] for t in trucks)
        servable: list[dict[str, Any]] = []
        for d in routable:
            qty_pos = float(d.get("quantity_positions") or 0)
            qty_kg = float(d.get("quantity_kg") or 0)
            if qty_pos > max_truck_cap:
                unassigned.append({
                    **self._clean_stop(d),
                    "unassigned_reason": (
                        f"{int(qty_pos)} positions exceeds the largest "
                        f"truck ({max_truck_cap}) — needs a delivery split"
                    ),
                })
            elif qty_kg > max_truck_kg:
                unassigned.append({
                    **self._clean_stop(d),
                    "unassigned_reason": (
                        f"{int(qty_kg)} kg exceeds the largest truck "
                        f"({int(max_truck_kg)} kg) — needs a delivery split"
                    ),
                })
            else:
                servable.append(d)

        if servable:
            # Step 3: travel-time matrix. Depot↔client legs use the authoritative
            # road km from the client directory; client↔client legs (same zone,
            # usually short) use straight-line distance with a road factor. Time
            # is derived consistently from distance ÷ average truck speed.
            dur_min = self._build_matrix(servable, depot)
            for i, d in enumerate(servable):
                d["_mi"] = i + 1

            # Step 4: assign deliveries to trucks (pins honoured, rest clustered).
            groups = self._assign_to_trucks(servable, trucks)

            # Step 5: order + schedule each truck.
            overflow_all: list[dict[str, Any]] = []
            for truck in trucks:
                items = groups.get(truck["truck_id"], [])
                if not items:
                    continue
                overflow_all.extend(self._schedule_truck(truck, items, dur_min))

            # Step 6: rescue pass. A truck that finished its zone early (or stayed
            # idle) can still run an extra depot→drop→depot trip. Place each
            # overflowed delivery on a truck that can legally carry it (positions
            # AND weight) and complete the round trip inside the working day and
            # the customer's time window. This stops servable drops being thrown
            # away while owned trucks sit idle.
            for d in self._rescue_overflow(trucks, overflow_all):
                reason = d.get("unassigned_reason") or "Exceeds working hours"
                unassigned.append({**self._clean_stop(d), "unassigned_reason": reason})

        clean_trucks = [self._clean_truck(t) for t in trucks]

        return {
            "plan_id": int(datetime.utcnow().timestamp()),
            "day": day.isoformat(),
            "source_file": source_path.name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "algorithm": "clustered VRPTW scheduler with OR-Tools time-window ordering",
            "depot": {"lat": depot[0], "lon": depot[1]},
            "work_window": {"start": self.cfg.work_start, "end": self.cfg.work_end},
            "selection": selection,
            "summary": {
                "source_rows": len(plan_data["rows"]),
                "selected_rows": len(rows),
                "selected_delivery_rows": len(delivery_rows),
                "deliveries_considered": len(deliveries),
                "deliveries_routed": len(routable),
                "total_positions": int(sum(d.get("quantity_positions") or 0 for d in deliveries)),
                "total_gross_weight_kg": round(sum(d.get("quantity_kg") or 0 for d in deliveries), 2),
            },
            "trucks": clean_trucks,
            "unassigned": [self._clean_stop(d) for d in unassigned],
        }

    # ------------------------------------------------------------ travel time
    def _build_matrix(
        self, routable: list[dict[str, Any]], depot: tuple[float, float]
    ) -> list[list[float]]:
        """Symmetric travel-time matrix (minutes), node 0 = depot.

        Depot↔client legs use the directory's real road km; client↔client legs
        use straight-line distance × a road-winding factor. Every leg's time is
        distance ÷ average truck speed, so displayed km and scheduled time stay
        consistent (and we never trust a possibly-wrong coordinate for the
        depot distance when the table already gives the real km)."""
        speed = self.cfg.avg_speed_kmh
        n = len(routable)
        depot_km: list[float] = []
        for d in routable:
            table_km = d.get("_table_km")
            km = (
                float(table_km) if table_km is not None
                else _haversine_km(depot[0], depot[1], d["lat"], d["lon"]) * ROAD_WINDING_FACTOR
            )
            depot_km.append(km)
            d["distance_km"] = round(km, 1)

        size = n + 1
        dur = [[0.0] * size for _ in range(size)]
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
        # region needs the fewest trips. The rented truck (id 999) is kept as a
        # last resort even though it is large, so we never pay for a rental while
        # an owned truck sits idle. Trucks already holding pins go last.
        trucks_sorted = sorted(
            trucks,
            key=lambda t: (
                len(groups[t["truck_id"]]) > 0,
                t["truck_id"] == self.RENTED_TRUCK_ID,
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
            choice = next(
                (t for t in available
                 if t["capacity_positions"] >= max_pos and t["capacity_kg"] >= max_kg),
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

    # The hired truck is only used once every owned vehicle is committed.
    RENTED_TRUCK_ID = 999

    def _schedule_truck(
        self, truck: dict[str, Any], items: list[dict[str, Any]], dur_min: list[list[float]]
    ) -> list[dict[str, Any]]:
        """Order the truck's stops, then walk them into depot-rooted trips,
        opening a new trip when capacity is full or a time window forces a long
        wait. Returns the deliveries that did not fit the working day."""
        order = self._order_stops(items, dur_min)
        capacity = truck["capacity_positions"]
        cap_kg = float(truck["capacity_kg"])
        work_end = self._minutes(self.cfg.work_end)

        cursor = self._minutes(self.cfg.work_start)  # truck free-at-depot time
        overflow: list[dict[str, Any]] = []

        trip_stops: list[dict[str, Any]] = []
        depart_at = float(cursor)
        load = 0.0       # positions on the open trip
        load_kg = 0.0    # gross weight on the open trip
        t = float(cursor)
        prev = 0  # depot node

        def close_trip() -> None:
            nonlocal cursor, trip_stops, load, load_kg, prev, t, depart_at
            if not trip_stops:
                return
            return_at = t + dur_min[prev][0]
            if return_at > work_end:
                overflow.extend({
                    **stop,
                    "unassigned_reason": "Trip cannot return before the working day ends",
                } for stop in trip_stops)
                trip_stops = []
                load = 0.0
                load_kg = 0.0
                prev = 0
                t = float(cursor)
                depart_at = float(cursor)
                return
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
            prev = 0
            t = float(cursor)
            depart_at = float(cursor)

        for d in order:
            mi = d["_mi"]
            qty = float(d.get("quantity_positions") or 0)
            qty_kg = float(d.get("quantity_kg") or 0)
            if qty > capacity or qty_kg > cap_kg:
                # Servable in principle (it fits a bigger truck), but every
                # larger truck is already committed to a heavier zone today.
                limit = (
                    f"{capacity} positions" if qty > capacity
                    else f"{int(cap_kg)} kg"
                )
                overflow.append({
                    **d,
                    "unassigned_reason": (
                        f"{qty:.0f} pos / {qty_kg:.0f} kg exceeds this truck's "
                        f"{limit} — all larger trucks are committed today"
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
                or forced_wait > self.LONG_WAIT_SPLIT_MIN
            ):
                close_trip()
                in_trip = False

            if not in_trip:
                # Leaving the depot fresh: depart late enough to roll straight
                # into the window instead of idling at the customer.
                leg = dur_min[0][mi]
                start = cursor
                if win_start is not None:
                    start = max(cursor, win_start - int(round(leg)))
                depart_at = start
                t = float(start)
                prev = 0
                arrival = t + leg

            if win_start is not None and arrival < win_start:
                arrival = float(win_start)
            service = self._service_minutes(d)
            service_end = arrival + service

            if service_end > work_end or (win_end is not None and arrival > win_end):
                overflow.append({
                    **d,
                    "unassigned_reason": (
                        "Outside customer time window"
                        if win_end is not None and arrival > win_end
                        else "Exceeds working hours"
                    ),
                })
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
        work_end = self._minutes(self.cfg.work_end)
        speed = self.cfg.avg_speed_kmh

        def free_at(truck: dict[str, Any]) -> int:
            if truck["trips"]:
                return self._minutes(truck["trips"][-1]["return_at"]) + self.cfg.reload_minutes
            return work_start

        still: list[dict[str, Any]] = []
        ordered = sorted(
            overflow,
            key=lambda d: (float(d.get("quantity_kg") or 0), float(d.get("quantity_positions") or 0)),
            reverse=True,
        )
        for d in ordered:
            qty = float(d.get("quantity_positions") or 0)
            qty_kg = float(d.get("quantity_kg") or 0)
            km = d.get("distance_km")
            if km is None:
                still.append(d)
                continue
            leg = float(km) / speed * 60.0
            service = self._service_minutes(d)
            window = d.get("constraints", {}).get("time_window")
            win_start = self._minutes(window[0]) if window else None
            win_end = self._minutes(window[1]) if window else None

            candidates = [
                t for t in trucks
                if t["capacity_positions"] >= qty and float(t["capacity_kg"]) >= qty_kg
            ]
            # Owned before hired, smallest adequate first, then earliest free.
            candidates.sort(key=lambda t: (
                t["truck_id"] == self.RENTED_TRUCK_ID,
                t["capacity_positions"],
                free_at(t),
            ))

            placed = False
            for t in candidates:
                start = free_at(t)
                if win_start is not None:
                    start = max(start, win_start - int(round(leg)))
                arrival = start + leg
                if win_start is not None and arrival < win_start:
                    arrival = float(win_start)
                service_end = arrival + service
                return_at = service_end + leg
                if service_end > work_end or return_at > work_end:
                    continue
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
        if HAS_ORTOOLS:
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
            horizon = self._minutes(self.cfg.work_end)
            routing.AddDimension(time_cb, horizon, horizon, False, "Time")
            time_dim = routing.GetDimensionOrDie("Time")
            time_dim.CumulVar(routing.Start(0)).SetRange(
                self._minutes(self.cfg.work_start),
                self._minutes(self.cfg.work_end),
            )
            time_dim.CumulVar(routing.End(0)).SetRange(
                self._minutes(self.cfg.work_start),
                self._minutes(self.cfg.work_end),
            )

            for local_pos, delivery in enumerate(items, start=1):
                index = manager.NodeToIndex(local_pos)
                window = delivery["constraints"].get("time_window")
                if window:
                    start = self._minutes(window[0])
                    end = self._minutes(window[1])
                else:
                    start = self._minutes(self.cfg.work_start)
                    end = self._minutes(self.cfg.work_end)
                time_dim.CumulVar(index).SetRange(start, end)

            params = pywrapcp.DefaultRoutingSearchParameters()
            params.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            params.time_limit.FromSeconds(3)
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
            params.time_limit.FromSeconds(2)
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
    def _clean_truck(truck: dict[str, Any]) -> dict[str, Any]:
        return {
            "truck_id": truck["truck_id"],
            "truck_label": truck["truck_label"],
            "capacity_positions": truck["capacity_positions"],
            "capacity_kg": truck["capacity_kg"],
            "trips": truck["trips"],
        }

    @staticmethod
    def _clean_stop(delivery: dict[str, Any]) -> dict[str, Any]:
        keep = (
            "id", "client", "start_location", "end_location", "quantity_positions",
            "position_count", "quantity_kg", "etd", "eta", "priority", "status",
            "constraints", "raw", "lat", "lon", "distance_km", "resolved_location",
            "travel_min", "unassigned_reason",
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
        gross_weight = self._weight_from_row(row)
        positions = float(row.get("position_count") or row.get("quantity") or 0)
        return {
            "id": int(row.get("row_number") or 0),
            "client": row.get("client") or row.get("end_location") or "Unknown client",
            "start_location": row.get("start_location") or "COFICAB Mégrine",
            "end_location": row.get("end_location") or row.get("client") or "Unknown destination",
            "quantity_positions": positions,
            "position_count": positions,
            "quantity_kg": gross_weight,
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
        minutes = max(0, min(minutes, 23 * 60 + 59))
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
