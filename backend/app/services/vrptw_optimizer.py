"""
VRPTW Optimizer — Vehicle Routing Problem with Time Windows

Two optimizer classes:
  VrptwOptimizer  — DB-aware, reads Camion/Chauffeur/DemandeLocal, materializes PlanVersion
  VRPTWOptimizer  — dict-based, used by /api/optimization/planning/generate (legacy UI)

Both use geographic K-means zone clustering so that:
  1. Each route covers a spatially compact area (dense, tight zones).
  2. No road segment is traversed by more than one truck — zone isolation
     guarantees that every arc (i→j) belongs to exactly one zone's route.
  3. Capacity constraints are respected per vehicle.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# COFICAB Sidi Hassine depot
DEPOT_LAT: float = 36.7708
DEPOT_LON: float = 10.1103
SERVICE_TIME_MINUTES: int = 15
SHIFT_START_MIN: int = 8 * 60   # 08:00
SHIFT_END_MIN: int = 18 * 60    # 18:00
DEFAULT_SPEED_KMH: int = 60
FUEL_L_PER_100KM: float = 30.0
MAX_TRIPS_PER_TRUCK: int = 3

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore[import]
    HAS_ORTOOLS = True
except ImportError:
    try:
        from ortools.routing import enums as _r_enums                          # type: ignore[import]
        from ortools.routing import routing_index_manager                       # type: ignore[import]
        from ortools.routing import routing_model as _rm                        # type: ignore[import]
        pywrapcp = routing_index_manager                                        # type: ignore[assignment]
        routing_enums_pb2 = _r_enums                                           # type: ignore[assignment]
        HAS_ORTOOLS = True
    except ImportError:
        HAS_ORTOOLS = False
        log.warning("OR-Tools not installed; VRPTW will use nearest-neighbour greedy")


# ────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2.0 * 6371.0 * math.asin(math.sqrt(max(0.0, h)))


# ────────────────────────────────────────────────────────────────────────────
# Geographic K-means++ zone clustering
# ────────────────────────────────────────────────────────────────────────────

def cluster_zones(
    latlons: List[Tuple[float, float]],
    k: int,
    max_iter: int = 30,
) -> List[List[int]]:
    """
    Partition delivery points into k geographic zones using K-means++.

    Returns a list of k lists, each containing 0-indexed positions into latlons.
    Empty clusters are kept so the list always has length k; callers should
    filter before iterating.

    Zone-isolation property
    -----------------------
    Each delivery belongs to exactly one zone, and each zone is served by
    exactly one vehicle.  Therefore every arc (i→j) appears in at most one
    vehicle's route across the full plan — no road segment is repeated.
    """
    n = len(latlons)
    if n == 0:
        return [[] for _ in range(k)]
    k = min(k, n)
    if k == 1:
        return [list(range(n))]

    import random
    rng = random.Random(42)  # deterministic across runs

    # K-means++ initialization: spread initial centroids to maximise coverage
    centroids: List[Tuple[float, float]] = [latlons[rng.randrange(n)]]
    for _ in range(k - 1):
        dists = [
            min(_haversine_km(p[0], p[1], c[0], c[1]) for c in centroids)
            for p in latlons
        ]
        total = sum(dists)
        if total == 0:
            centroids.append(latlons[rng.randrange(n)])
            continue
        r = rng.random() * total
        cumulative = 0.0
        for i, d in enumerate(dists):
            cumulative += d
            if cumulative >= r:
                centroids.append(latlons[i])
                break
        else:
            centroids.append(latlons[-1])

    clusters: List[List[int]] = [[] for _ in range(k)]
    for _ in range(max_iter):
        new_clusters: List[List[int]] = [[] for _ in range(k)]
        for i, p in enumerate(latlons):
            nearest = min(
                range(k),
                key=lambda c: _haversine_km(p[0], p[1], centroids[c][0], centroids[c][1]),
            )
            new_clusters[nearest].append(i)

        new_centroids: List[Tuple[float, float]] = []
        for ci, zone in enumerate(new_clusters):
            if zone:
                avg_lat = sum(latlons[j][0] for j in zone) / len(zone)
                avg_lon = sum(latlons[j][1] for j in zone) / len(zone)
                new_centroids.append((avg_lat, avg_lon))
            else:
                new_centroids.append(centroids[ci])

        if new_clusters == clusters:
            break
        clusters, centroids = new_clusters, new_centroids

    return clusters


def capacity_aware_cluster(
    latlons: List[Tuple[float, float]],
    qtys: List[int],
    capacities: List[int],
) -> List[List[int]]:
    """Build compact geographic clusters while respecting position capacity."""
    n = len(latlons)
    k = len(capacities)
    if n == 0:
        return [[] for _ in range(k)]
    if k == 0:
        return []
    if k == 1:
        return [list(range(n))]

    target_fill_pct = 0.80

    def _angle(idx: int) -> float:
        lat, lon = latlons[idx]
        return math.atan2(lon - DEPOT_LON, lat - DEPOT_LAT)

    polar_order = sorted(range(n), key=_angle)
    truck_order = sorted(range(k), key=lambda i: capacities[i], reverse=True)
    clusters: List[List[int]] = [[] for _ in range(k)]
    cluster_loads: List[int] = [0] * k
    assigned = [False] * n

    for truck_rank, ci in enumerate(truck_order):
        cap = max(0, capacities[ci])
        if cap <= 0:
            continue
        target = max(1, int(cap * target_fill_pct))
        centroid_lat = DEPOT_LAT
        centroid_lon = DEPOT_LON

        while cluster_loads[ci] < cap:
            best_idx = None
            best_dist = float("inf")
            for di in polar_order:
                if assigned[di]:
                    continue
                if cluster_loads[ci] + qtys[di] > cap:
                    continue
                dist = _haversine_km(
                    centroid_lat, centroid_lon,
                    latlons[di][0], latlons[di][1],
                )
                if dist < best_dist:
                    best_dist = dist
                    best_idx = di

            if best_idx is None:
                break

            clusters[ci].append(best_idx)
            cluster_loads[ci] += qtys[best_idx]
            assigned[best_idx] = True

            centroid_lat = sum(latlons[j][0] for j in clusters[ci]) / len(clusters[ci])
            centroid_lon = sum(latlons[j][1] for j in clusters[ci]) / len(clusters[ci])

            remaining_unassigned = sum(1 for value in assigned if not value)
            trucks_left = k - truck_rank - 1
            if cluster_loads[ci] >= target and trucks_left > 0 and remaining_unassigned > 0:
                break

    for di in polar_order:
        if assigned[di]:
            continue
        best_ci = None
        best_room = -1
        for ci in range(k):
            room = capacities[ci] - cluster_loads[ci]
            if room >= qtys[di] and room > best_room:
                best_room = room
                best_ci = ci
        if best_ci is None:
            best_ci = min(range(k), key=lambda i: cluster_loads[i])
        clusters[best_ci].append(di)
        cluster_loads[best_ci] += qtys[di]
        assigned[di] = True

    return clusters


def _rebalance_for_capacity(
    clusters: List[List[int]],
    qty_per_point: List[float],
    capacities: List[float],
) -> Tuple[List[List[int]], List[int]]:
    """
    If any cluster's total quantity exceeds its truck's capacity, move the
    heaviest overflowing node to the least-loaded cluster that has room.
    """
    unassigned: List[int] = []
    default_cap = capacities[-1] if capacities else float("inf")

    for _ in range(len(qty_per_point) * 2):
        changed = False
        for ci, cluster in enumerate(clusters):
            cap = capacities[ci] if ci < len(capacities) else default_cap
            total = sum(qty_per_point[j] for j in cluster)
            if total <= cap:
                continue
            changed = True
            heaviest_local = max(range(len(cluster)), key=lambda x: qty_per_point[cluster[x]])
            node = cluster.pop(heaviest_local)
            node_qty = qty_per_point[node]
            placed = False
            for other_ci, other_cluster in enumerate(clusters):
                if other_ci == ci:
                    continue
                other_cap = capacities[other_ci] if other_ci < len(capacities) else default_cap
                if sum(qty_per_point[j] for j in other_cluster) + node_qty <= other_cap:
                    other_cluster.append(node)
                    placed = True
                    break
            if not placed:
                unassigned.append(node)
        if not changed:
            break
    return clusters, unassigned


# ────────────────────────────────────────────────────────────────────────────
# DB-aware optimizer
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class OptimizerWeights:
    alpha: float = 1.0    # distance cost weight
    beta: float = 2.0     # delay penalty (applied to late-arrival soft penalty)
    gamma: float = 1.5    # underutilisation penalty (100 - load_pct)
    delta: float = 3.0    # premium freight cost
    epsilon: float = 1.0  # fuel consumption weight


@dataclass
class OptimizerConfig:
    depot_lat: float = DEPOT_LAT
    depot_lon: float = DEPOT_LON
    time_limit_sec: int = 60
    speed_kmh: int = DEFAULT_SPEED_KMH
    service_time_min: int = SERVICE_TIME_MINUTES
    work_window_hours: int = 10
    weights: OptimizerWeights = field(default_factory=OptimizerWeights)


class VrptwOptimizer:
    """
    DB-aware VRPTW optimizer.

    Algorithm
    ---------
    1. Load Camion(DISPONIBLE), Chauffeur(ACTIF), DemandeLocal(NOUVELLE, date=day).
    2. K-means++ geographic clustering: partition deliveries into k zones
       where k = number of available trucks.
    3. Capacity rebalancing: move overflow nodes to neighbouring zones.
    4. Assign the heaviest zone to the largest-capacity truck.
    5. For each zone, solve a single-vehicle VRPTW with OR-Tools
       (nearest-neighbour greedy if OR-Tools is unavailable).
    6. Materialise: PlanVersion(DRAFT) → PlanMission rows → MissionDemande rows.

    Zone-isolation guarantee
    ------------------------
    Since each zone is served by exactly one truck, no arc (i→j) can appear
    in more than one vehicle's route.  This eliminates redundant traversals of
    the same road segments across the full delivery plan.
    """

    def __init__(self, db: Any, cfg: Optional[OptimizerConfig] = None) -> None:
        self.db = db
        self.cfg = cfg or OptimizerConfig()

    def plan(self, day: date, weights: Optional[OptimizerWeights] = None) -> Any:
        from app.models.plan import (
            PlanVersion, PlanMission, MissionDemande,
            StatutPlan, StatutMission, ModeMission, Periode,
        )
        from app.models.camion import Camion, CamionStatus
        from app.models.chauffeur import Chauffeur, ChauffeurStatus
        from app.models.demande import DemandeLocal, StatutDemande

        if weights:
            self.cfg.weights = weights

        trucks = self.db.query(Camion).filter(Camion.status == CamionStatus.DISPONIBLE).all()
        if not trucks:
            raise ValueError("No available trucks (status=DISPONIBLE) in fleet")

        drivers = self.db.query(Chauffeur).filter(Chauffeur.status == ChauffeurStatus.ACTIF).all()
        if not drivers:
            raise ValueError("No active drivers available for this day")

        demandes = (
            self.db.query(DemandeLocal)
            .filter(
                DemandeLocal.date_livraison == day,
                DemandeLocal.statut == StatutDemande.NOUVELLE,
            )
            .all()
        )
        if not demandes:
            raise ValueError(f"No pending demandes for {day}")

        # Build node list — node 0 = depot, nodes 1..N = deliveries
        valid_demandes = []
        for demande in demandes:
            positions = self._get_positions(demande)
            if positions <= 0:
                log.warning(
                    "Demande %s skipped: positions=%s",
                    getattr(demande, "id", "?"),
                    positions,
                )
                continue
            valid_demandes.append(demande)

        if not valid_demandes:
            raise ValueError(f"All demandes for {day} have zero positions")

        nodes = self._build_nodes(valid_demandes)
        delivery_idx = list(range(1, len(nodes)))  # 1-indexed positions in nodes[]

        # Step 2: geographic clustering
        latlons = [(nodes[i]["lat"], nodes[i]["lon"]) for i in delivery_idx]
        qtys = [int(nodes[i]["qty"]) for i in delivery_idx]
        trucks_sorted = sorted(trucks, key=self._get_truck_capacity, reverse=True)
        capacities = [self._get_truck_capacity(t) for t in trucks_sorted]
        raw_clusters = capacity_aware_cluster(latlons, qtys, capacities)
        # Convert 0-indexed latlons positions → 1-indexed nodes positions
        node_clusters = [
            [delivery_idx[j] for j in zone]
            for zone in raw_clusters
        ]

        # Step 3: capacity rebalancing
        # Convert to 0-indexed delivery positions for rebalancer
        flat = [[j - 1 for j in zone] for zone in node_clusters]
        flat, unassigned_flat = _rebalance_for_capacity(
            flat,
            [nodes[i]["qty"] for i in delivery_idx],
            [float(c) for c in capacities],
        )
        node_clusters = [[j + 1 for j in zone] for zone in flat]

        if unassigned_flat:
            skipped = [nodes[j + 1]["demande_id"] for j in unassigned_flat]
            log.warning(
                "VrptwOptimizer: %d deliveries exceed all truck capacities and will be skipped: %s",
                len(unassigned_flat), skipped,
            )

        assignments = [
            (trucks_sorted[idx], zone)
            for idx, zone in enumerate(node_clusters)
            if idx < len(trucks_sorted) and zone
        ]

        dist_m = self._build_dist_matrix(nodes)

        # Create plan version
        last = self.db.query(PlanVersion).order_by(PlanVersion.plan_id.desc()).first()
        plan_num = (last.plan_id + 1) if last else 1
        version = PlanVersion(
            plan_id=plan_num,
            version_number=1,
            periode=Periode.JOUR,
            date_debut=day,
            date_fin=day,
            statut_plan=StatutPlan.DRAFT,
            commentaire=(
                f"VrptwOptimizer — {len(assignments)} zones, "
                f"{len(valid_demandes)} demandes, zone-isolated routes"
            ),
        )
        self.db.add(version)
        self.db.flush()

        # Step 5 + 6: solve each zone and materialise
        for truck_idx, (truck, zone_nodes) in enumerate(assignments):
            if not zone_nodes:
                continue
            driver = self._assign_driver(truck, drivers, truck_idx)
            ordered = self._solve_zone(nodes, zone_nodes, truck, dist_m)
            if not ordered:
                continue

            total_qty = sum(nodes[i]["qty"] for i in ordered)
            total_kg = sum(nodes[i]["kg"] for i in ordered)
            total_km = self._route_km(ordered, dist_m)
            truck_capacity = float(self._get_truck_capacity(truck))
            load_pct = round(total_qty / truck_capacity * 100, 2) if truck_capacity else 0.0
            fuel_rate = float(truck.consommation_base_l_100km or FUEL_L_PER_100KM)
            fuel_l = total_km * fuel_rate / 100.0
            cost_transport = round(total_km * 1.20, 2)  # €1.20/km baseline

            mission = PlanMission(
                plan_version_id=version.id,
                camion_id=truck.id,
                chauffeur_id=driver.id,
                date_mission=day,
                statut=StatutMission.PLANIFIEE,
                mode=ModeMission.NORMAL,
                km_parcourus=round(total_km, 2),
                charge_kg=round(total_kg, 2),
                charge_palettes=int(total_qty),
                load_eff_pallets_pct=load_pct,
                load_eff_pct=load_pct,
                fuel_consomme_l=round(fuel_l, 2),
                cout_transport_eur=cost_transport,
            )
            self.db.add(mission)
            self.db.flush()

            for order, node_i in enumerate(ordered, start=1):
                demande = nodes[node_i]["demande"]
                self.db.add(MissionDemande(
                    mission_id=mission.id,
                    demande_id=demande.id,
                    ordre_livraison=order,
                ))
                demande.statut = StatutDemande.PLANIFIEE

        self.db.commit()
        return version

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _get_positions(demande: Any) -> int:
        for attr in ("nb_positions", "nombre_palettes", "positions"):
            val = getattr(demande, attr, None)
            if val is not None:
                try:
                    return max(0, int(float(val)))
                except (TypeError, ValueError):
                    return 0
        return 0

    @staticmethod
    def _get_truck_capacity(truck: Any) -> int:
        for attr in ("max_palettes", "nombre_palettes", "capacite_palettes", "nb_palettes"):
            val = getattr(truck, attr, None)
            if val is not None:
                try:
                    return max(1, int(float(val)))
                except (TypeError, ValueError):
                    break
        log.warning(
            "Truck %s has no palette capacity field; defaulting to 33",
            getattr(truck, "id", "?"),
        )
        return 33

    def _solve_zone(
        self,
        nodes: List[Dict],
        zone_indices: List[int],
        truck: Any,
        dist_m: List[List[float]],
    ) -> List[int]:
        """
        Single-vehicle VRPTW for one geographic zone.
        Returns node indices in delivery order.
        Since this is a single-vehicle route, every arc (i→j) in the result
        appears nowhere else in the full plan (zone-isolation guarantee).
        """
        if not zone_indices:
            return []
        if len(zone_indices) == 1 or not HAS_ORTOOLS:
            return self._greedy_order(zone_indices, dist_m)

        # Local remap: local index 0 = depot, 1..M = zone deliveries
        local_to_global = [0] + zone_indices
        n_local = len(local_to_global)

        try:
            manager = pywrapcp.RoutingIndexManager(n_local, 1, 0)
            routing = pywrapcp.RoutingModel(manager)
        except Exception:
            return self._greedy_order(zone_indices, dist_m)

        w = self.cfg.weights
        fuel_rate = float(truck.consommation_base_l_100km or FUEL_L_PER_100KM)

        def cost_cb(from_idx: int, to_idx: int) -> int:
            g_i = local_to_global[manager.IndexToNode(from_idx)]
            g_j = local_to_global[manager.IndexToNode(to_idx)]
            km = dist_m[g_i][g_j]
            fuel_l = km * fuel_rate / 100.0
            return int(w.alpha * km * 100 + w.epsilon * fuel_l * 10)

        cost_cb_idx = routing.RegisterTransitCallback(cost_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(cost_cb_idx)

        def demand_cb(idx: int) -> int:
            return int(nodes[local_to_global[manager.IndexToNode(idx)]]["qty"])

        dem_idx = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            dem_idx, 0, [self._get_truck_capacity(truck)], True, "Capacity"
        )

        def time_cb(from_idx: int, to_idx: int) -> int:
            g_i = local_to_global[manager.IndexToNode(from_idx)]
            g_j = local_to_global[manager.IndexToNode(to_idx)]
            travel = int(round(dist_m[g_i][g_j] / self.cfg.speed_kmh * 60))
            service = 0 if manager.IndexToNode(to_idx) == 0 else self.cfg.service_time_min
            return travel + service

        time_cb_idx = routing.RegisterTransitCallback(time_cb)
        routing.AddDimension(time_cb_idx, 30, SHIFT_END_MIN, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        time_dim.CumulVar(routing.Start(0)).SetRange(SHIFT_START_MIN, SHIFT_END_MIN)
        time_dim.CumulVar(routing.End(0)).SetRange(SHIFT_START_MIN, SHIFT_END_MIN)

        for local_i, global_i in enumerate(local_to_global):
            if local_i == 0:
                continue
            start, end = nodes[global_i]["window"]
            start = max(start, SHIFT_START_MIN)
            end = min(end, SHIFT_END_MIN)
            if end < start:
                end = start
            time_dim.CumulVar(manager.NodeToIndex(local_i)).SetRange(start, end)

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.FromSeconds(min(self.cfg.time_limit_sec, 30))

        solution = routing.SolveWithParameters(params)
        if solution is None:
            log.warning("Zone solver found no solution; using nearest-neighbour greedy fallback")
            return self._greedy_order(zone_indices, dist_m)

        idx = routing.Start(0)
        ordered: List[int] = []
        while not routing.IsEnd(idx):
            local_node = manager.IndexToNode(idx)
            if local_node != 0:
                ordered.append(local_to_global[local_node])
            idx = solution.Value(routing.NextVar(idx))
        return ordered

    def _greedy_order(self, indices: List[int], dist_m: List[List[float]]) -> List[int]:
        remaining = list(indices)
        ordered: List[int] = []
        current = 0
        while remaining:
            nearest = min(remaining, key=lambda j: dist_m[current][j])
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest
        return ordered

    def _route_km(self, ordered: List[int], dist_m: List[List[float]]) -> float:
        if not ordered:
            return 0.0
        km = dist_m[0][ordered[0]]
        for i in range(len(ordered) - 1):
            km += dist_m[ordered[i]][ordered[i + 1]]
        km += dist_m[ordered[-1]][0]
        return km

    def _build_nodes(self, demandes: list) -> List[Dict]:
        nodes: List[Dict] = [{
            "lat": self.cfg.depot_lat,
            "lon": self.cfg.depot_lon,
            "kg": 0.0,
            "qty": 0,
            "window": (SHIFT_START_MIN, SHIFT_END_MIN),
            "demande": None,
            "demande_id": None,
        }]
        for d in demandes:
            c = d.client
            lat = float(c.latitude) if c.latitude else self.cfg.depot_lat
            lon = float(c.longitude) if c.longitude else self.cfg.depot_lon
            start = (
                c.fenetre_ouverture.hour * 60 + c.fenetre_ouverture.minute
                if c.fenetre_ouverture else SHIFT_START_MIN
            )
            end = (
                c.fenetre_fermeture.hour * 60 + c.fenetre_fermeture.minute
                if c.fenetre_fermeture else SHIFT_END_MIN
            )
            start = max(start, SHIFT_START_MIN)
            end = min(end, SHIFT_END_MIN)
            if end < start:
                end = start
            nodes.append({
                "lat": lat,
                "lon": lon,
                "qty": self._get_positions(d),
                "kg": float(d.quantite_kg),
                "window": (start, end),
                "demande": d,
                "demande_id": d.id,
            })
        return nodes

    def _build_dist_matrix(self, nodes: List[Dict]) -> List[List[float]]:
        n = len(nodes)
        m = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    m[i][j] = _haversine_km(
                        nodes[i]["lat"], nodes[i]["lon"],
                        nodes[j]["lat"], nodes[j]["lon"],
                    )
        return m

    def _assign_driver(self, truck: Any, drivers: list, fallback_idx: int) -> Any:
        if getattr(truck, "chauffeur_defaut_id", None):
            for d in drivers:
                if d.id == truck.chauffeur_defaut_id:
                    return d
        return drivers[fallback_idx % len(drivers)]


# ────────────────────────────────────────────────────────────────────────────
# Dict-based optimizer (legacy frontend planning UI)
# ────────────────────────────────────────────────────────────────────────────

class VRPTWOptimizer:
    """
    Dict-based VRPTW optimizer used by /api/optimization/planning/generate.

    Enhanced with geographic zone clustering:
    - Deliveries are pre-partitioned into spatially compact zones (one per truck).
    - OR-Tools enforces zone assignments via SetAllowedVehiclesForIndex so the
      solver cannot route truck A through zone B's stops.
    - The greedy fallback processes each truck's zone deliveries independently.
    - No road segment appears in more than one vehicle's route.
    """

    def __init__(
        self,
        deliveries: List[Dict[str, Any]],
        trucks: List[Dict[str, Any]],
        current_routes: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.deliveries = deliveries
        self.trucks = trucks
        self.current_routes = current_routes or []

    def optimize(self) -> Dict[str, Any]:
        cost_before = self._calculate_before_cost()

        zero_qty: List[Dict] = []
        self._oversized_deliveries: List[Dict] = []
        max_capacity = max((int(t.get("capacity", 0)) for t in self.trucks), default=0)
        filtered = []
        for d in self.deliveries:
            q = self._delivery_qty(d)
            if q <= 0:
                zero_qty.append(d)
            elif q > max_capacity > 0:
                self._oversized_deliveries.append(d)
            else:
                filtered.append(d)

        original_deliveries = self.deliveries
        self.deliveries = filtered

        if HAS_ORTOOLS:
            try:
                result = self._optimize_with_ortools()
                result["status"] = "success"
                result["algorithm"] = "OR-Tools VRPTW (zone-clustered, positions)"
            except Exception as exc:
                log.error("OR-Tools optimization failed: %s — falling back to greedy", exc)
                result = self._optimize_greedy()
                result["status"] = "success"
                result["algorithm"] = "Greedy VRPTW (zone-clustered, positions)"
        else:
            result = self._optimize_greedy()
            result["status"] = "success"
            result["algorithm"] = "Greedy VRPTW (zone-clustered, positions)"

        total_after = result["costs"].get("total_cost", 0.0)
        savings = round(cost_before - total_after, 2)
        savings_pct = round((savings / cost_before * 100) if cost_before > 0 else 0.0, 1)

        result["costs"]["before"] = round(cost_before, 2)
        result["costs"]["after"] = round(total_after, 2)
        result["costs"]["savings"] = savings
        result["costs"]["savings_percent"] = savings_pct
        result["current_routes"] = self.current_routes

        if zero_qty:
            result.setdefault("skipped_zero_qty", []).extend(zero_qty)
            result.setdefault("suggestions", []).append({
                "type": "ZERO_QTY",
                "severity": "warning",
                "message": f"{len(zero_qty)} delivery row(s) ignored because positions = 0.",
                "action": "Check position/palette quantity in the planning data.",
            })

        if self._oversized_deliveries:
            result.setdefault("unassigned", []).extend(self._oversized_deliveries)
            result.setdefault("suggestions", []).append({
                "type": "CAPACITY",
                "severity": "high",
                "message": (
                    "Some deliveries exceed the maximum truck position capacity and were not assigned: "
                    + ", ".join(
                        str(d.get("row_number") or d.get("id") or d.get("customer"))
                        for d in self._oversized_deliveries
                    )
                ),
                "action": "Increase truck capacity or split the delivery.",
            })

        self.deliveries = original_deliveries
        return result

    # ---------------------------------------------------------------- OR-Tools

    def _optimize_with_ortools(self) -> Dict[str, Any]:
        if not self.deliveries or not self.trucks:
            return self._build_result([], self.deliveries)

        vehicle_instances = self._build_vehicle_instances()
        num_vehicles = len(vehicle_instances)
        trips_per_truck = max(1, num_vehicles // max(len(self.trucks), 1))

        # Geographic clustering — one zone per truck
        latlons = [
            (float(d.get("lat", DEPOT_LAT)), float(d.get("lng", DEPOT_LON)))
            for d in self.deliveries
        ]
        zone_clusters = capacity_aware_cluster(
            latlons,
            [self._delivery_qty(d) for d in self.deliveries],
            [int(t.get("capacity", 33)) for t in self.trucks],
        )
        # Map: 0-indexed delivery position → zone index (= truck index)
        delivery_to_zone: Dict[int, int] = {}
        for zone_idx, zone in enumerate(zone_clusters):
            for pos in zone:
                delivery_to_zone[pos] = zone_idx

        try:
            from ortools.routing import routing_index_manager as rim
            from ortools.routing import routing_model as rm
            manager = rim.RoutingIndexManager(len(self.deliveries) + 1, num_vehicles, 0)
            routing = rm.RoutingModel(manager)
            enums_mod = routing_enums_pb2
        except Exception:
            manager = pywrapcp.RoutingIndexManager(len(self.deliveries) + 1, num_vehicles, 0)
            routing = pywrapcp.RoutingModel(manager)
            enums_mod = routing_enums_pb2

        def _dist(node_a: int, node_b: int) -> float:
            lat_a, lng_a = (DEPOT_LAT, DEPOT_LON) if node_a == 0 else (
                float(self.deliveries[node_a - 1].get("lat", DEPOT_LAT)),
                float(self.deliveries[node_a - 1].get("lng", DEPOT_LON)),
            )
            lat_b, lng_b = (DEPOT_LAT, DEPOT_LON) if node_b == 0 else (
                float(self.deliveries[node_b - 1].get("lat", DEPOT_LAT)),
                float(self.deliveries[node_b - 1].get("lng", DEPOT_LON)),
            )
            return _haversine_km(lat_a, lng_a, lat_b, lng_b)

        def cost_cb(from_idx: int, to_idx: int) -> int:
            return int(_dist(manager.IndexToNode(from_idx), manager.IndexToNode(to_idx)) * 100)

        transit_idx = routing.RegisterTransitCallback(cost_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        def demand_cb(from_idx: int) -> int:
            node = manager.IndexToNode(from_idx)
            return 0 if node == 0 else self._delivery_qty(self.deliveries[node - 1])

        demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx, 0,
            [vi["capacity"] for vi in vehicle_instances],
            True, "Capacity",
        )

        def time_cb(from_idx: int, to_idx: int) -> int:
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            km = _dist(from_node, to_node)
            travel = int(km / DEFAULT_SPEED_KMH * 60)
            service = 0 if from_node == 0 else SERVICE_TIME_MINUTES
            return travel + service

        time_cb_idx = routing.RegisterTransitCallback(time_cb)
        routing.AddDimension(time_cb_idx, 30, SHIFT_END_MIN, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")

        for pos, delivery in enumerate(self.deliveries):
            node_idx = pos + 1
            index = manager.NodeToIndex(node_idx)
            earliest = int(delivery.get("earliest_time", SHIFT_START_MIN))
            latest = int(delivery.get("latest_time", SHIFT_END_MIN))
            earliest = max(earliest, SHIFT_START_MIN)
            latest = min(latest, SHIFT_END_MIN)
            if latest < earliest:
                latest = earliest
            time_dim.CumulVar(index).SetRange(earliest, latest)
            routing.AddDisjunction([index], 10000)

            # Zone isolation: restrict this delivery to its zone's vehicle instances
            zone_idx = delivery_to_zone.get(pos, 0)
            allowed = [
                zone_idx * trips_per_truck + t
                for t in range(trips_per_truck)
                if zone_idx * trips_per_truck + t < num_vehicles
            ]
            if allowed:
                routing.SetAllowedVehiclesForIndex(allowed, index)

        for vid in range(num_vehicles):
            start_idx = routing.Start(vid)
            end_idx = routing.End(vid)
            time_dim.CumulVar(start_idx).SetRange(SHIFT_START_MIN, SHIFT_END_MIN)
            time_dim.CumulVar(end_idx).SetRange(SHIFT_START_MIN, SHIFT_END_MIN)
            routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(start_idx))
            routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(end_idx))

        try:
            params = routing.DefaultSearchParameters()
        except AttributeError:
            params = pywrapcp.DefaultRoutingSearchParameters()

        try:
            params.first_solution_strategy = enums_mod.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            params.local_search_metaheuristic = enums_mod.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        except AttributeError:
            pass
        params.time_limit.FromSeconds(10)

        solution = routing.SolveWithParameters(params)
        if not solution:
            return self._optimize_greedy()

        return self._parse_solution(routing, manager, solution, vehicle_instances)

    # ---------------------------------------------------------------- greedy

    def _optimize_greedy(self) -> Dict[str, Any]:
        if not self.deliveries or not self.trucks:
            return self._build_result([], self.deliveries)

        vehicle_instances = self._build_vehicle_instances()
        trips_per_truck = max(1, len(vehicle_instances) // max(len(self.trucks), 1))

        # Geographic clustering: each truck handles its own zone
        latlons = [
            (float(d.get("lat", DEPOT_LAT)), float(d.get("lng", DEPOT_LON)))
            for d in self.deliveries
        ]
        zone_clusters = capacity_aware_cluster(
            latlons,
            [self._delivery_qty(d) for d in self.deliveries],
            [int(t.get("capacity", 33)) for t in self.trucks],
        )

        routes: List[Dict] = []
        all_unassigned: List[Dict] = []

        for truck_idx, truck in enumerate(self.trucks):
            zone_pos = zone_clusters[truck_idx] if truck_idx < len(zone_clusters) else []
            # Sort zone deliveries by quantity descending for best bin-packing
            zone_deliveries = sorted(
                [self.deliveries[j] for j in zone_pos],
                key=self._delivery_qty,
                reverse=True,
            )
            remaining = list(zone_deliveries)
            capacity = int(truck.get("capacity", 33))

            for trip_idx in range(trips_per_truck):
                if not remaining:
                    break
                vi_idx = truck_idx * trips_per_truck + trip_idx
                vi = (
                    vehicle_instances[vi_idx]
                    if vi_idx < len(vehicle_instances)
                    else {"truck_id": truck.get("id"), "capacity": capacity, "trip_number": trip_idx + 1}
                )

                stops: List[Dict] = []
                current_time = SHIFT_START_MIN
                prev_lat, prev_lng = DEPOT_LAT, DEPOT_LON
                total_distance = 0.0
                total_quantity = 0
                assigned_indices: List[int] = []

                open_indices = list(range(len(remaining)))
                while open_indices:
                    best_idx = None
                    best_dist = float("inf")
                    for idx in open_indices:
                        delivery = remaining[idx]
                        quantity = self._delivery_qty(delivery)
                        if total_quantity + quantity > capacity:
                            continue
                        lat = float(delivery.get("lat", DEPOT_LAT))
                        lng = float(delivery.get("lng", DEPOT_LON))
                        dist = _haversine_km(prev_lat, prev_lng, lat, lng)
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = idx

                    if best_idx is None:
                        break

                    delivery = remaining[best_idx]
                    quantity = self._delivery_qty(delivery)
                    lat = float(delivery.get("lat", DEPOT_LAT))
                    lng = float(delivery.get("lng", DEPOT_LON))
                    travel_time = int(best_dist / DEFAULT_SPEED_KMH * 60)
                    current_time += travel_time

                    earliest = max(int(delivery.get("earliest_time", SHIFT_START_MIN)), SHIFT_START_MIN)
                    latest = min(int(delivery.get("latest_time", SHIFT_END_MIN)), SHIFT_END_MIN)
                    if latest < earliest:
                        latest = earliest
                    if current_time < earliest:
                        status = "EARLY"
                        current_time = earliest
                    elif current_time > latest:
                        status = "LATE"
                    else:
                        status = "OK"

                    departure = current_time + SERVICE_TIME_MINUTES
                    stops.append({
                        "client_id": delivery.get("id"),
                        "client_name": delivery.get("customer"),
                        "arrival_time": current_time,
                        "departure_time": departure,
                        "status": status,
                        "quantity": quantity,
                    })
                    current_time = departure
                    total_distance += best_dist
                    total_quantity += quantity
                    prev_lat, prev_lng = lat, lng
                    assigned_indices.append(best_idx)
                    open_indices.remove(best_idx)

                for idx in sorted(assigned_indices, reverse=True):
                    remaining.pop(idx)

                if stops:
                    ret_dist = _haversine_km(prev_lat, prev_lng, DEPOT_LAT, DEPOT_LON)
                    current_time += int(ret_dist / DEFAULT_SPEED_KMH * 60)
                    total_distance += ret_dist
                    routes.append({
                        "truck_id": vi["truck_id"],
                        "trip_number": vi.get("trip_number", trip_idx + 1),
                        "capacity": capacity,
                        "load": total_quantity,
                        "stops": stops,
                        "start_time": SHIFT_START_MIN,
                        "end_time": current_time,
                        "total_distance": round(total_distance, 2),
                        "total_cost": round(50.0 + total_distance * 0.5, 2),
                        "utilization_percent": round(total_quantity / capacity * 100, 1) if capacity else 0,
                    })

            all_unassigned.extend(remaining)

        return self._build_result(routes, all_unassigned)

    # ---------------------------------------------------------------- shared

    @staticmethod
    def _delivery_qty(delivery: Dict[str, Any]) -> int:
        for key in ("nb_positions", "positions", "quantity", "position_count"):
            val = delivery.get(key)
            if val is not None:
                try:
                    return max(0, int(float(val)))
                except (TypeError, ValueError):
                    return 0
        return 0

    def _build_vehicle_instances(self) -> List[Dict[str, Any]]:
        total_qty = sum(self._delivery_qty(d) for d in self.deliveries)
        total_cap = sum(int(t.get("capacity", 33)) for t in self.trucks) or 1
        trips_needed = max(1, math.ceil(total_qty / total_cap))
        trips_per_truck = min(MAX_TRIPS_PER_TRUCK, trips_needed)

        instances = []
        for truck in self.trucks:
            for trip_idx in range(trips_per_truck):
                instances.append({
                    "truck_id": truck.get("id"),
                    "truck_type": truck.get("type"),
                    "capacity": int(truck.get("capacity", 33)),
                    "trip_number": trip_idx + 1,
                })
        return instances

    def _calculate_before_cost(self) -> float:
        if not self.current_routes:
            total = 0.0
            for d in self.deliveries:
                km = _haversine_km(
                    DEPOT_LAT, DEPOT_LON,
                    float(d.get("lat", DEPOT_LAT)),
                    float(d.get("lng", DEPOT_LON)),
                )
                total += 50.0 + km * 2 * 0.5
            return total
        return sum(50.0 + float(r.get("total_distance", 0)) * 0.5 for r in self.current_routes)

    def _build_result(
        self,
        routes: List[Dict[str, Any]],
        unassigned: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_distance = sum(r.get("total_distance", 0) for r in routes)
        total_cost = sum(r.get("total_cost", 0) for r in routes)
        total_positions = sum(
            sum(float(s.get("quantity", 0)) for s in r.get("stops", []))
            for r in routes
        )
        avg_util = round(
            sum(r.get("utilization_percent", 0) for r in routes) / len(routes)
            if routes else 0,
            1,
        )
        suggestions: List[Dict] = []
        if not routes:
            suggestions.append({
                "type": "EMPTY_PLAN",
                "severity": "warning",
                "message": "No route could be planned with the available trucks.",
                "action": "Check delivery positions, truck capacities, and time windows.",
            })
        if unassigned:
            suggestions.append({
                "type": "UNASSIGNED",
                "severity": "high",
                "message": "Some deliveries could not be assigned due to capacity or time-window constraints.",
                "action": "Split oversized deliveries, add a rented truck, or adjust time windows.",
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
                "total_positions": int(total_positions),
                "total_weight": int(total_positions),
                "total_distance": round(total_distance, 2),
                "total_time_minutes": sum(
                    r.get("end_time", 0) - r.get("start_time", 0) for r in routes
                ),
                "avg_utilization_percent": avg_util,
            },
        }

    def _parse_solution(
        self,
        routing: Any,
        manager: Any,
        solution: Any,
        vehicle_instances: List[Dict],
    ) -> Dict[str, Any]:
        routes: List[Dict] = []
        assigned_ids: set = set()
        time_dim = routing.GetDimensionOrDie("Time")

        for vid in range(routing.vehicles()):
            vi = vehicle_instances[vid]
            stops: List[Dict] = []
            total_distance = 0.0
            route_qty = 0
            prev_lat, prev_lng = DEPOT_LAT, DEPOT_LON

            index = routing.Start(vid)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node > 0:
                    delivery = self.deliveries[node - 1]
                    quantity = self._delivery_qty(delivery)
                    lat = float(delivery.get("lat", DEPOT_LAT))
                    lng = float(delivery.get("lng", DEPOT_LON))
                    dist = _haversine_km(prev_lat, prev_lng, lat, lng)
                    arrival = solution.Value(time_dim.CumulVar(index))
                    departure = arrival + SERVICE_TIME_MINUTES
                    earliest = max(int(delivery.get("earliest_time", SHIFT_START_MIN)), SHIFT_START_MIN)
                    latest = min(int(delivery.get("latest_time", SHIFT_END_MIN)), SHIFT_END_MIN)
                    if latest < earliest:
                        latest = earliest
                    status = "EARLY" if arrival < earliest else ("LATE" if arrival > latest else "OK")
                    stops.append({
                        "client_id": delivery.get("id"),
                        "client_name": delivery.get("customer"),
                        "arrival_time": arrival,
                        "departure_time": departure,
                        "status": status,
                        "quantity": quantity,
                    })
                    total_distance += dist
                    route_qty += quantity
                    prev_lat, prev_lng = lat, lng
                    assigned_ids.add(delivery.get("id"))
                index = solution.Value(routing.NextVar(index))

            if stops:
                end_time = solution.Value(time_dim.CumulVar(routing.End(vid)))
                routes.append({
                    "truck_id": vi["truck_id"],
                    "trip_number": vi.get("trip_number", 1),
                    "capacity": vi["capacity"],
                    "load": route_qty,
                    "stops": stops,
                    "start_time": solution.Value(time_dim.CumulVar(routing.Start(vid))),
                    "end_time": end_time,
                    "total_distance": round(total_distance, 2),
                    "total_cost": round(50.0 + total_distance * 0.5, 2),
                    "utilization_percent": round(route_qty / max(vi["capacity"], 1) * 100, 1),
                })

        unassigned = [d for d in self.deliveries if d.get("id") not in assigned_ids]
        return self._build_result(routes, unassigned)
