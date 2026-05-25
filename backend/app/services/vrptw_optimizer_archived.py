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
            return 0.0

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
            suggestions.append("Aucun trajet n'a pu être planifié avec les camions disponibles.")
        if unassigned:
            suggestions.append(
                "Certaines livraisons n'ont pas pu être assignées en raison de contraintes de capacité ou de fenêtres horaires."
            )

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
