"""
VRPTW Optimizer - Vehicle Routing Problem with Time Windows
Utilise OR-Tools pour générer des routes optimisées
"""

from typing import List, Dict, Any, Tuple
import logging
import math

logger = logging.getLogger(__name__)

DEPOT_LOCATION = (36.5, 10.1)
SERVICE_TIME_MINUTES = 15
DRIVE_TIME_FACTOR = 2
MAX_TRIPS_PER_TRUCK = 3

try:
    from ortools.linear_solver import pywraplp  # type: ignore[import]
    from ortools.routing import enums  # type: ignore[import]
    from ortools.routing import routing_index_manager  # type: ignore[import]
    from ortools.routing import routing_model  # type: ignore[import]
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False
    logger.warning("OR-Tools not installed. Install with: pip install ortools")


class VRPTWOptimizer:
    """Optimiseur de routage avec fenêtres horaires (VRPTW)"""

    def __init__(
        self,
        deliveries: List[Dict[str, Any]],
        trucks: List[Dict[str, Any]],
        current_routes: List[Dict[str, Any]] = None,
    ):
        self.deliveries = deliveries
        self.trucks = trucks
        self.current_routes = current_routes or []
        self.routes = []

    def optimize(self) -> Dict[str, Any]:
        """
        Génère les routes optimisées
        Fallback sur algorithme greedy si OR-Tools n'est pas disponible
        """
        cost_before = self._calculate_before_cost()

        # Pre-check: any delivery that has quantity > max truck capacity cannot be assigned
        self._oversized_deliveries = []
        max_capacity = max((int(t.get("capacity", 0)) for t in self.trucks), default=0)
        if max_capacity <= 0:
            max_capacity = 0
        filtered = []
        for d in self.deliveries:
            q = int(float(d.get("quantity", 0))) if d.get("quantity") is not None else 0
            if q > max_capacity and max_capacity > 0:
                self._oversized_deliveries.append(d)
            else:
                filtered.append(d)

        # Use filtered deliveries for optimization; keep original list in current_routes
        original_deliveries = self.deliveries
        self.deliveries = filtered

        if HAS_ORTOOLS:
            try:
                result = self._optimize_with_ortools()
                result["status"] = "success"
                result["algorithm"] = "OR-Tools VRPTW"
            except Exception as e:
                logger.error(f"OR-Tools optimization failed: {e}. Using greedy algorithm.")
                result = self._optimize_greedy()
                result["status"] = "success"
                result["algorithm"] = "Greedy VRPTW"
        else:
            logger.info("Using greedy algorithm (OR-Tools not available)")
            result = self._optimize_greedy()
            result["status"] = "success"
            result["algorithm"] = "Greedy VRPTW"

        total_after = result["costs"].get("total_cost", 0.0)
        savings = round(cost_before - total_after, 2)
        savings_percent = round((savings / cost_before * 100) if cost_before > 0 else 0.0, 1)

        result["costs"]["before"] = round(cost_before, 2)
        result["costs"]["after"] = round(total_after, 2)
        result["costs"]["savings"] = savings
        result["costs"]["savings_percent"] = savings_percent
        result["current_routes"] = self.current_routes

        # Append oversized deliveries to unassigned with suggestion
        if self._oversized_deliveries:
            if "unassigned" not in result:
                result["unassigned"] = []
            result["unassigned"].extend(self._oversized_deliveries)
            msg = (
                "Certaines livraisons dépassent la capacité maximale d'un camion et n'ont pas pu être assignées: "
                + ", ".join(str(d.get("row_number") or d.get("id") or d.get("customer")) for d in self._oversized_deliveries)
            )
            if "suggestions" not in result:
                result["suggestions"] = []
            result["suggestions"].append({"type": "CAPACITY", "severity": "high", "message": msg, "action": "Increase truck capacity or split delivery into multiple positions."})

        # restore original deliveries
        self.deliveries = original_deliveries

        return result

    def _build_vehicle_instances(self) -> List[Dict[str, Any]]:
        vehicle_instances = []
        total_quantity = sum(int(float(d.get("quantity", 0))) for d in self.deliveries)
        total_capacity = sum(int(t.get("capacity", 10000)) for t in self.trucks) or 1
        trips_needed = max(1, math.ceil(total_quantity / total_capacity))
        trips_per_truck = min(MAX_TRIPS_PER_TRUCK, trips_needed)

        for truck in self.trucks:
            capacity = int(truck.get("capacity", 10000))
            for trip_idx in range(trips_per_truck):
                vehicle_instances.append({
                    "truck_id": truck.get("id"),
                    "truck_type": truck.get("type"),
                    "capacity": capacity,
                    "trip_number": trip_idx + 1,
                })

        return vehicle_instances

    def _calculate_before_cost(self) -> float:
        if not self.current_routes:
            total = 0.0
            for delivery in self.deliveries:
                lat = float(delivery.get("lat", DEPOT_LOCATION[0]))
                lng = float(delivery.get("lng", DEPOT_LOCATION[1]))
                round_trip = 2 * math.sqrt(
                    ((lat - DEPOT_LOCATION[0]) * 111) ** 2 +
                    ((lng - DEPOT_LOCATION[1]) * 111 * math.cos(math.radians((lat + DEPOT_LOCATION[0]) / 2))) ** 2
                )
                total += 50.0 + round_trip * 0.5
            return total

        return sum(
            50.0 + float(route.get("total_distance", 0)) * 0.5
            for route in self.current_routes
        )

    def _build_result(self, routes: List[Dict[str, Any]], unassigned: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_distance = sum(r.get("total_distance", 0) for r in routes)
        total_cost = sum(r.get("total_cost", 0) for r in routes)
        total_weight = sum(
            sum(float(s.get("quantity", 0)) for s in r.get("stops", []))
            for r in routes
        )
        avg_util = round(
            sum(r.get("utilization_percent", 0) for r in routes) / len(routes)
            if routes
            else 0,
            1,
        )

        suggestions = []
        if not routes:
            suggestions.append({
                "type": "EMPTY_PLAN",
                "severity": "warning",
                "message": "No route could be planned with the available trucks.",
                "action": "Check delivery quantities, truck capacities, and time windows.",
            })
        if unassigned:
            suggestions.append({
                "type": "UNASSIGNED",
                "severity": "high",
                "message": "Some deliveries could not be assigned because of capacity or time-window constraints.",
                "action": "Split oversized deliveries, add a rented truck, or adjust the time window.",
            })

        return {
            "routes": routes,
            "unassigned": unassigned,
            "costs": {
                "before": round(total_cost, 2),
                "after": round(total_cost, 2),
                "savings": 0.0,
                "savings_percent": 0.0,
                "total_distance": round(total_distance, 2),
                "total_cost": round(total_cost, 2),
                "route_count": len(routes),
            },
            "suggestions": suggestions,
            "metrics": {
                "total_routes": len(routes),
                "total_deliveries": sum(len(r.get("stops", [])) for r in routes),
                "total_weight": int(total_weight),
                "total_distance": round(total_distance, 2),
                "total_time_minutes": sum(r.get("end_time", 0) - r.get("start_time", 0) for r in routes),
                "avg_utilization_percent": avg_util,
            },
        }

    def _optimize_with_ortools(self) -> Dict[str, Any]:
        """Optimisation avec OR-Tools"""
        if not self.deliveries or not self.trucks:
            return self._build_result([], self.deliveries)

        vehicle_instances = self._build_vehicle_instances()
        num_vehicles = len(vehicle_instances)
        depot = 0

        manager = routing_index_manager.RoutingIndexManager(
            len(self.deliveries) + 1, num_vehicles, depot
        )
        routing = routing_model.RoutingModel(manager)

        def distance_between(node_a, node_b):
            if node_a == 0:
                lat_a, lng_a = DEPOT_LOCATION
            else:
                lat_a = float(self.deliveries[node_a - 1].get("lat", DEPOT_LOCATION[0]))
                lng_a = float(self.deliveries[node_a - 1].get("lng", DEPOT_LOCATION[1]))

            if node_b == 0:
                lat_b, lng_b = DEPOT_LOCATION
            else:
                lat_b = float(self.deliveries[node_b - 1].get("lat", DEPOT_LOCATION[0]))
                lng_b = float(self.deliveries[node_b - 1].get("lng", DEPOT_LOCATION[1]))

            lat_diff = (lat_a - lat_b) * 111
            lng_diff = (lng_a - lng_b) * 111 * math.cos(math.radians((lat_a + lat_b) / 2))
            return math.sqrt(lat_diff ** 2 + lng_diff ** 2)

        def cost_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_between(from_node, to_node) * 100)

        transit_callback_index = routing.RegisterTransitCallback(cost_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        def demand_callback(from_index):
            node = manager.IndexToNode(from_index)
            if node == 0:
                return 0
            return int(float(self.deliveries[node - 1].get("quantity", 0)))

        demand_callback_index = routing.RegisterTransitCallback(demand_callback)
        vehicle_capacities = [vehicle["capacity"] for vehicle in vehicle_instances]
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            vehicle_capacities,
            True,
            "Capacity"
        )

        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)

            if from_node == 0:
                lat_a, lng_a = DEPOT_LOCATION
                service_time = 0
            else:
                lat_a = float(self.deliveries[from_node - 1].get("lat", DEPOT_LOCATION[0]))
                lng_a = float(self.deliveries[from_node - 1].get("lng", DEPOT_LOCATION[1]))
                service_time = SERVICE_TIME_MINUTES

            if to_node == 0:
                lat_b, lng_b = DEPOT_LOCATION
            else:
                lat_b = float(self.deliveries[to_node - 1].get("lat", DEPOT_LOCATION[0]))
                lng_b = float(self.deliveries[to_node - 1].get("lng", DEPOT_LOCATION[1]))

            dist = math.sqrt(
                ((lat_a - lat_b) * 111) ** 2 +
                ((lng_a - lng_b) * 111 * math.cos(math.radians((lat_a + lat_b) / 2))) ** 2
            )
            travel_time = int(dist * DRIVE_TIME_FACTOR)
            return travel_time + service_time

        time_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_callback_index,
            1020,
            1020,
            False,
            "Time"
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        for idx, delivery in enumerate(self.deliveries, start=1):
            index = manager.NodeToIndex(idx)
            earliest = int(delivery.get("earliest_time", 480))
            latest = int(delivery.get("latest_time", 1020))
            time_dimension.CumulVar(index).SetRange(earliest, latest)
            routing.AddDisjunction([index], 10000)

        for vehicle_id in range(num_vehicles):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)
            time_dimension.CumulVar(start_index).SetRange(480, 1020)
            time_dimension.CumulVar(end_index).SetRange(480, 1020)
            routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(start_index))
            routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(end_index))

        search_parameters = routing.DefaultSearchParameters()
        search_parameters.first_solution_strategy = (
            enums.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            enums.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(10)

        solution = routing.SolveWithParameters(search_parameters)
        if not solution:
            return self._optimize_greedy()

        return self._parse_solution(routing, manager, solution, vehicle_instances)

    def _optimize_greedy(self) -> Dict[str, Any]:
        """
        Algorithme greedy simple :
        - Trier les livraisons par nombre de palettes décroissant
        - Assigner aux camions et à plusieurs voyages si nécessaire
        """
        if not self.deliveries or not self.trucks:
            return self._build_result([], self.deliveries)

        routes = []
        remaining = sorted(self.deliveries, key=lambda x: float(x.get("quantity", 0)), reverse=True)
        vehicle_instances = self._build_vehicle_instances()

        for vehicle_info in vehicle_instances:
            if not remaining:
                break

            stops = []
            current_time = 480
            prev_lat, prev_lng = DEPOT_LOCATION
            total_distance = 0.0
            total_quantity = 0

            assigned_indices = []
            for idx in range(len(remaining) - 1, -1, -1):
                delivery = remaining[idx]
                quantity = float(delivery.get("quantity", 0))
                if total_quantity + quantity > vehicle_info["capacity"]:
                    continue

                lat = float(delivery.get("lat", DEPOT_LOCATION[0]))
                lng = float(delivery.get("lng", DEPOT_LOCATION[1]))
                dist = math.sqrt(
                    ((lat - prev_lat) * 111) ** 2 +
                    ((lng - prev_lng) * 111 * math.cos(math.radians((lat + prev_lat) / 2))) ** 2
                )
                travel_time = int(dist * DRIVE_TIME_FACTOR)
                current_time += travel_time

                earliest = int(delivery.get("earliest_time", 480))
                latest = int(delivery.get("latest_time", 1020))
                if current_time < earliest:
                    status = "EARLY"
                    current_time = earliest
                elif current_time > latest:
                    status = "LATE"
                else:
                    status = "OK"

                departure_time = current_time + SERVICE_TIME_MINUTES
                stops.append({
                    "client_id": delivery.get("id"),
                    "client_name": delivery.get("customer"),
                    "arrival_time": current_time,
                    "departure_time": departure_time,
                    "status": status,
                    "quantity": int(quantity),
                })

                current_time = departure_time
                total_distance += dist
                total_quantity += int(quantity)
                prev_lat, prev_lng = lat, lng
                assigned_indices.append(idx)

            for idx in sorted(assigned_indices, reverse=True):
                remaining.pop(idx)

            if stops:
                return_to_depot = math.sqrt(
                    ((prev_lat - DEPOT_LOCATION[0]) * 111) ** 2 +
                    ((prev_lng - DEPOT_LOCATION[1]) * 111 * math.cos(math.radians((prev_lat + DEPOT_LOCATION[0]) / 2))) ** 2
                )
                current_time += int(return_to_depot * DRIVE_TIME_FACTOR)
                total_distance += return_to_depot
                route_cost = round(50.0 + total_distance * 0.5, 2)
                utilization = round(total_quantity / vehicle_info["capacity"] * 100, 1)

                routes.append({
                    "truck_id": vehicle_info["truck_id"],
                    "trip_number": vehicle_info["trip_number"],
                    "capacity": vehicle_info["capacity"],
                    "load": total_quantity,
                    "stops": stops,
                    "start_time": 480,
                    "end_time": current_time,
                    "total_distance": round(total_distance, 2),
                    "total_cost": route_cost,
                    "utilization_percent": utilization,
                })

        return self._build_result(routes, remaining)

    def _parse_solution(self, routing, manager, solution, vehicle_instances) -> Dict[str, Any]:
        """Parse la solution OR-Tools"""
        routes = []
        assigned_ids = set()
        time_dimension = routing.GetDimensionOrDie("Time")

        for vehicle_id in range(routing.vehicles()):
            vehicle_info = vehicle_instances[vehicle_id]
            truck_id = vehicle_info["truck_id"]
            capacity = vehicle_info["capacity"]
            stops = []
            total_distance = 0.0
            route_quantity = 0
            prev_lat, prev_lng = DEPOT_LOCATION

            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index > 0:
                    delivery = self.deliveries[node_index - 1]
                    quantity = float(delivery.get("quantity", 0))
                    lat = float(delivery.get("lat", DEPOT_LOCATION[0]))
                    lng = float(delivery.get("lng", DEPOT_LOCATION[1]))
                    dist = math.sqrt(
                        ((lat - prev_lat) * 111) ** 2 +
                        ((lng - prev_lng) * 111 * math.cos(math.radians((lat + prev_lat) / 2))) ** 2
                    )
                    arrival_time = solution.Value(time_dimension.CumulVar(index))
                    departure_time = arrival_time + SERVICE_TIME_MINUTES
                    earliest = int(delivery.get("earliest_time", 480))
                    latest = int(delivery.get("latest_time", 1020))
                    if arrival_time < earliest:
                        status = "EARLY"
                    elif arrival_time > latest:
                        status = "LATE"
                    else:
                        status = "OK"

                    stops.append({
                        "client_id": delivery.get("id"),
                        "client_name": delivery.get("customer"),
                        "arrival_time": arrival_time,
                        "departure_time": departure_time,
                        "status": status,
                        "quantity": int(quantity),
                    })
                    total_distance += dist
                    route_quantity += int(quantity)
                    prev_lat, prev_lng = lat, lng
                    assigned_ids.add(delivery.get("id"))

                index = solution.Value(routing.NextVar(index))

            if stops:
                end_time = solution.Value(time_dimension.CumulVar(routing.End(vehicle_id)))
                route_cost = round(50.0 + total_distance * 0.5, 2)
                utilization = round(route_quantity / max(capacity, 1) * 100, 1)

                routes.append({
                    "truck_id": truck_id,
                    "trip_number": vehicle_info["trip_number"],
                    "capacity": capacity,
                    "load": route_quantity,
                    "stops": stops,
                    "start_time": solution.Value(time_dimension.CumulVar(routing.Start(vehicle_id))),
                    "end_time": end_time,
                    "total_distance": round(total_distance, 2),
                    "total_cost": route_cost,
                    "utilization_percent": utilization,
                })

        unassigned = [d for d in self.deliveries if d.get("id") not in assigned_ids]
        return self._build_result(routes, unassigned)

    @staticmethod
    def _empty_metrics() -> Dict[str, int]:
        return {
            "total_routes": 0,
            "total_deliveries": 0,
            "total_weight": 0,
            "total_time_minutes": 0,
            "avg_utilization_percent": 0,
        }
