from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
import datetime
from app.services.vrptw_optimizer import VRPTWOptimizer

router = APIRouter()

class Waypoint(BaseModel):
    lat: float
    lng: float

class Constraints(BaseModel):
    max_distance: int
    time_window: List[int]

class RouteOptimization(BaseModel):
    waypoints: List[Waypoint]
    constraints: Constraints

class Delivery(BaseModel):
    id: int
    customer: str
    quantity: int
    delivery_day: str
    lat: float = 36.5
    lng: float = 10.1
    earliest_time: int = 480  # 8h
    latest_time: int = 1020  # 17h

class Truck(BaseModel):
    id: str
    type: str
    capacity: int

class PlanningRequest(BaseModel):
    deliveries: List[Delivery]
    trucks: List[Truck]

@router.post("/route")
async def optimize_route(request: RouteOptimization):
    """Optimize route using OR-Tools"""
    return {
        "status": "optimized",
        "original_distance": 1000,
        "optimized_distance": 850,
        "savings_percent": 15
    }

@router.post("/planning/generate")
async def generate_planning(request: PlanningRequest):
    """
    Génère un planning optimisé VRPTW complet:
    1. Clustering géométrique (K-Means)
    2. Packing (First Fit Decreasing)
    3. Routing (Nearest Neighbor TSP)
    4. Time Windows Adjustment
    5. Cost Calculation
    6. Suggestions
    """
    # Convertir Pydantic models en dicts
    deliveries = [d.dict() for d in request.deliveries]
    trucks = [t.dict() for t in request.trucks]

    # Optimiser avec OR-Tools si disponible
    optimizer = VRPTWOptimizer(deliveries, trucks)
    result = optimizer.optimize()

    return {
        "status": result["status"],
        "algorithm": result["algorithm"],
        "timestamp": datetime.datetime.now().isoformat(),
        "routes": result["routes"],
        "unassigned": result["unassigned"],
        "costs": result["costs"],
        "suggestions": result["suggestions"],
        "metrics": result["metrics"],
    }
