from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from app.services.vrptw_complete_optimizer import VRPTWCompleteOptimizer

router = APIRouter()


class PlanningGenerateRequest(BaseModel):
    deliveries: List[Dict[str, Any]]
    trucks: List[Dict[str, Any]] = []
    current_routes: List[Dict[str, Any]] = []


@router.post("/planning/generate")
async def generate_planning(request: PlanningGenerateRequest):
    """Generate a planning using VRPTWCompleteOptimizer and return structured plan."""
    try:
        optimizer = VRPTWCompleteOptimizer(request.deliveries, request.trucks, request.current_routes)
        result = optimizer.run()
        return {"status": "success", "plan": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")