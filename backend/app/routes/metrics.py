from fastapi import APIRouter
import datetime
import random

router = APIRouter()

@router.get("/kpi")
async def get_kpi():
    """Get current KPI metrics"""
    return {
        "planning_time": random.randint(85, 145),  # seconds
        "detection_latency": random.randint(8, 22),  # seconds
        "data_error_rate": round(random.uniform(0.002, 0.008), 4)  # percentage
    }