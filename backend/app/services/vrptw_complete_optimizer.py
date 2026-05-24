"""Standalone greedy VRPTW optimizer implementation."""

from typing import Any, Dict, List


class VRPTWCompleteOptimizer:
    def __init__(
        self,
        deliveries: List[Dict[str, Any]],
        trucks: List[Dict[str, Any]],
        current_routes: List[Dict[str, Any]] = None,
    ):
        self.deliveries = deliveries or []
        self.trucks = trucks or []
        self.current_routes = current_routes or []

    def run(self) -> Dict[str, Any]:
        if not self.deliveries:
            return {"routes": [], "status": "success", "algorithm": "greedy"}

        if not self.trucks:
            return {"routes": [], "status": "no_trucks", "algorithm": "greedy"}

        sorted_deliveries = sorted(
            self.deliveries,
            key=lambda item: item.get("quantity", 0),
            reverse=True,
        )

        routes: List[Dict[str, Any]] = []
        route_states: List[Dict[str, Any]] = []
        next_truck_index = 0

        def start_route(delivery: Dict[str, Any]) -> None:
            nonlocal next_truck_index
            truck = self.trucks[next_truck_index]
            truck_id = str(truck.get("id", next_truck_index))
            capacity = int(truck.get("capacity", 0))
            quantity = int(delivery.get("quantity", 0))
            route = {
                "truck_id": truck_id,
                "stops": [delivery.get("id")],
                "total_quantity": quantity,
            }
            remaining_capacity = max(capacity - quantity, 0)
            route_states.append({"route": route, "remaining_capacity": remaining_capacity, "locked": quantity > capacity})
            routes.append(route)
            next_truck_index = (next_truck_index + 1) % len(self.trucks)

        for delivery in sorted_deliveries:
            quantity = int(delivery.get("quantity", 0))
            placed = False

            for state in route_states:
                if state["locked"]:
                    continue
                if state["remaining_capacity"] >= quantity:
                    state["route"]["stops"].append(delivery.get("id"))
                    state["route"]["total_quantity"] += quantity
                    state["remaining_capacity"] -= quantity
                    placed = True
                    break

            if not placed:
                start_route(delivery)

        return {"routes": routes, "status": "success", "algorithm": "greedy"}
