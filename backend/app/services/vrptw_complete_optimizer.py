"""
VRPTW Optimizer Complet - Algorithme 6 étapes
1. Clustering géométrique (K-Means)
2. Packing (Bin Packing)
3. Routing (Nearest Neighbor TSP)
4. Time Windows Adjustment
5. Cost Calculation
6. Suggestions
"""

from typing import List, Dict, Any, Tuple
import math
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class Client:
    id: int
    name: str
    lat: float
    lng: float
    weight: float
    earliest_time: int  # minutes depuis minuit
    latest_time: int
    service_time: int = 15  # minutes

    def distance_to(self, other: 'Client') -> float:
        """Distance euclidienne en km (approximation)"""
        lat_diff = (self.lat - other.lat) * 111  # 1 deg lat ≈ 111km
        lng_diff = (self.lng - other.lng) * 111 * math.cos(math.radians(self.lat))
        return math.sqrt(lat_diff**2 + lng_diff**2)


@dataclass
class Truck:
    id: str
    capacity: float
    fixed_cost: float = 50.0  # €/jour
    variable_cost: float = 0.5  # €/km


@dataclass
class Stop:
    client: Client
    arrival_time: int  # minutes depuis minuit
    departure_time: int
    status: str  # "OK", "EARLY", "LATE"


@dataclass
class Route:
    truck: Truck
    stops: List[Stop]
    start_time: int = 480  # 08:00
    end_time: int = 1080  # 18:00
    total_distance: float = 0.0
    total_cost: float = 0.0


class VRPTWCompleteOptimizer:
    """Optimiseur VRPTW complet avec 6 étapes"""

    DEPOT = Client(0, "Dépôt", 0.0, 0.0, 0.0, 480, 1080)  # 8h-18h

    def __init__(self, clients: List[Dict], trucks: List[Dict]):
        self.clients = [self._dict_to_client(c) for c in clients]
        self.trucks = [self._dict_to_truck(t) for t in trucks]
        self.clusters = []
        self.routes = []
        self.unassigned = []

    @staticmethod
    def _dict_to_client(d: Dict) -> Client:
        quantity = d.get("quantity", d.get("total_gross_weight", 0))
        return Client(
            id=d.get("id", 0),
            name=d.get("customer", ""),
            lat=d.get("lat", 36.5),
            lng=d.get("lng", 10.1),
            weight=float(quantity or 0),  # stored as pallet count, not physical weight
            earliest_time=int(d.get("earliest_time", 480)),  # 8h
            latest_time=int(d.get("latest_time", 1020)),  # 17h
        )

    @staticmethod
    def _dict_to_truck(d: Dict) -> Truck:
        return Truck(
            id=d.get("id", ""),
            capacity=float(d.get("capacity", 10000)),
        )

    def optimize(self) -> Dict[str, Any]:
        """Exécute les 6 étapes"""
        logger.info("🚀 Démarrage optimisation VRPTW")

        # Étape 1: Clustering
        self.clusters = self._step1_clustering()
        logger.info(f"✅ Étape 1: {len(self.clusters)} clusters créés")

        # Étape 2: Packing
        self.assignments = self._step2_packing()
        logger.info(f"✅ Étape 2: Assignation clusters → camions")

        # Étape 3 & 4: Routing + Time Adjustment
        self.routes = self._step3_4_routing_and_time()
        logger.info(f"✅ Étape 3-4: {len(self.routes)} routes générées")

        # Étape 5: Coûts
        costs_before, costs_after = self._step5_cost_calculation()
        logger.info(f"✅ Étape 5: Économie = {costs_before - costs_after}€")

        # Étape 6: Suggestions
        suggestions = self._step6_suggestions()

        return {
            "status": "success",
            "algorithm": "VRPTW Complete (K-Means + FFD + NN + Time Windows)",
            "routes": [self._route_to_dict(r) for r in self.routes],
            "unassigned": [asdict(c) for c in self.unassigned],
            "costs": {
                "before": costs_before,
                "after": costs_after,
                "savings": costs_before - costs_after,
                "savings_percent": round(((costs_before - costs_after) / costs_before * 100) if costs_before > 0 else 0, 1),
            },
            "suggestions": suggestions,
            "metrics": {
                "total_routes": len(self.routes),
                "total_deliveries": sum(len(r.stops) for r in self.routes),
                "total_distance": sum(r.total_distance for r in self.routes),
                "avg_utilization": round(
                    sum(sum(s.client.weight for s in r.stops) / r.truck.capacity for r in self.routes) / len(self.routes) * 100
                    if self.routes else 0, 1
                ),
            },
        }

    def _step1_clustering(self, k: int = None) -> List[List[Client]]:
        """Étape 1: K-Means clustering"""
        if not self.clients:
            return []

        k = k or min(len(self.trucks), max(1, len(self.clients) // 5))
        clients = self.clients[:]

        # Initialiser centroïdes (premiers clients)
        centroids = clients[:k]

        for iteration in range(10):  # 10 itérations max
            # Assigner clients aux clusters
            clusters = [[] for _ in range(k)]
            for client in clients:
                closest = min(range(k), key=lambda i: client.distance_to(centroids[i]))
                clusters[closest].append(client)

            # Recalculer centroïdes
            new_centroids = []
            for cluster in clusters:
                if cluster:
                    avg_lat = sum(c.lat for c in cluster) / len(cluster)
                    avg_lng = sum(c.lng for c in cluster) / len(cluster)
                    new_centroids.append(Client(
                        id=-1, name="centroid", lat=avg_lat, lng=avg_lng,
                        weight=0, earliest_time=480, latest_time=1080
                    ))
                else:
                    new_centroids.append(centroids[len(new_centroids)])

            centroids = new_centroids

        # Retourner clusters non-vides
        return [c for c in clusters if c]

    def _step2_packing(self) -> Dict[str, str]:
        """Étape 2: First Fit Decreasing bin packing"""
        assignments = {}

        # Trier clusters par poids total (décroissant)
        sorted_clusters = sorted(
            self.clusters,
            key=lambda c: sum(cl.weight for cl in c),
            reverse=True
        )

        # Trier camions par capacité (décroissant)
        sorted_trucks = sorted(self.trucks, key=lambda t: t.capacity, reverse=True)

        truck_loads = {t.id: 0.0 for t in sorted_trucks}

        for cluster in sorted_clusters:
            cluster_weight = sum(c.weight for c in cluster)

            # First Fit: chercher premier camion qui peut le prendre
            assigned = False
            for truck in sorted_trucks:
                if truck_loads[truck.id] + cluster_weight <= truck.capacity:
                    for client in cluster:
                        assignments[client.id] = truck.id
                    truck_loads[truck.id] += cluster_weight
                    assigned = True
                    break

            if not assigned:
                # Aucun camion dispo
                for client in cluster:
                    self.unassigned.append(client)

        return assignments

    def _step3_4_routing_and_time(self) -> List[Route]:
        """Étape 3 & 4: Routing (NN) + Time Windows Adjustment"""
        truck_clients = {t.id: [] for t in self.trucks}

        for client in self.clients:
            truck_id = self.assignments.get(client.id)
            if truck_id and truck_id in truck_clients:
                truck_clients[truck_id].append(client)
            else:
                # Non assigné ou hors cluster
                continue

        routes = []

        for truck in self.trucks:
            clients_for_truck = truck_clients[truck.id]
            if not clients_for_truck:
                continue

            # Nearest Neighbor TSP
            route_clients = self._nearest_neighbor(clients_for_truck)

            # Générer stops avec time windows
            stops = []
            current_time = 480  # 8h
            previous_location = self.DEPOT

            for client in route_clients:
                travel_time = int(previous_location.distance_to(client) * 2)  # ~30km/h
                current_time += travel_time

                # Vérifier time window
                if current_time < client.earliest_time:
                    status = "EARLY"
                    current_time = client.earliest_time
                elif current_time > client.latest_time:
                    status = "LATE"
                else:
                    status = "OK"

                stop = Stop(
                    client=client,
                    arrival_time=current_time,
                    departure_time=current_time + client.service_time,
                    status=status
                )
                stops.append(stop)
                current_time = stop.departure_time
                previous_location = client

            # Retour dépôt
            return_time = int(previous_location.distance_to(self.DEPOT) * 2)
            end_time = current_time + return_time

            # Calculer distance totale
            total_distance = self.DEPOT.distance_to(route_clients[0])
            for i in range(len(route_clients) - 1):
                total_distance += route_clients[i].distance_to(route_clients[i + 1])
            total_distance += route_clients[-1].distance_to(self.DEPOT)

            route = Route(
                truck=truck,
                stops=stops,
                end_time=end_time,
                total_distance=total_distance,
            )
            routes.append(route)

        return routes

    def _nearest_neighbor(self, clients: List[Client]) -> List[Client]:
        """Nearest Neighbor TSP"""
        if not clients:
            return []

        route = [clients[0]]
        unvisited = set(c.id for c in clients[1:])

        current = clients[0]
        while unvisited:
            nearest = min(
                (c for c in clients if c.id in unvisited),
                key=lambda c: current.distance_to(c)
            )
            route.append(nearest)
            current = nearest
            unvisited.remove(nearest.id)

        return route

    def _step5_cost_calculation(self) -> Tuple[float, float]:
        """Étape 5: Calcul des coûts"""
        # Coût après optimisation
        cost_after = sum(r.truck.fixed_cost + r.total_distance * r.truck.variable_cost for r in self.routes)

        # Coût avant (estimation: tous les clients en camion individuel)
        cost_before = len(self.clients) * (self.trucks[0].fixed_cost + 50 * self.trucks[0].variable_cost)

        return cost_before, cost_after

    def _step6_suggestions(self) -> List[Dict]:
        """Étape 6: Suggestions"""
        suggestions = []

        # Clients non assignés
        if self.unassigned:
            suggestions.append({
                "type": "CAPACITY",
                "severity": "high",
                "message": f"{len(self.unassigned)} clients non assignés",
                "action": "Ajouter un camion ou reporter au jour suivant",
            })

        # Time windows conflicts
        late_stops = [s for r in self.routes for s in r.stops if s.status == "LATE"]
        if late_stops:
            suggestions.append({
                "type": "TIME_WINDOW",
                "severity": "warning",
                "message": f"{len(late_stops)} arrêts dépassent la plage horaire",
                "action": "Réorganiser la route ou notifier les clients",
            })

        # Utilisation moyenne faible
        avg_util = sum(sum(s.client.weight for s in r.stops) / r.truck.capacity for r in self.routes) / len(self.routes) if self.routes else 0
        if avg_util < 0.5:
            suggestions.append({
                "type": "UTILIZATION",
                "severity": "info",
                "message": f"Utilisation moyenne: {avg_util*100:.0f}%",
                "action": "Regrouper livraisons ou réduire nombre de camions",
            })

        return suggestions

    @staticmethod
    def _route_to_dict(route: Route) -> Dict:
        return {
            "truck_id": route.truck.id,
            "stops": [
                {
                    "client_id": s.client.id,
                    "client_name": s.client.name,
                    "arrival_time": s.arrival_time,
                    "departure_time": s.departure_time,
                    "status": s.status,
                }
                for s in route.stops
            ],
            "start_time": route.start_time,
            "end_time": route.end_time,
            "total_distance": round(route.total_distance, 2),
            "total_cost": round(route.truck.fixed_cost + route.total_distance * route.truck.variable_cost, 2),
        }
