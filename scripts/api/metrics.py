from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import random  # For demo data, replace with real metrics in production

router = APIRouter()

def generate_demo_data():
    """Generate demo metrics data. Replace with real metrics in production."""
    now = datetime.now()
    dates = [(now - timedelta(days=i)).strftime('%a') for i in range(6, -1, -1)]
    
    return {
        "activeCrawlers": random.randint(3, 8),
        "urlsProcessed": random.randint(1000, 2000),
        "averageProcessingTime": f"{random.uniform(1.5, 3.5):.1f}s",
        "dailyStats": {
            "processed": [random.randint(50, 150) for _ in range(7)],
            "dates": dates
        }
    }

@router.get("/api/v1/metrics")
async def get_metrics():
    """Get system metrics."""
    try:
        # In production, replace this with real metrics gathering
        return generate_demo_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 