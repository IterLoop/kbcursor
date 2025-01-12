from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum
import random  # For demo data, replace with real DB queries

router = APIRouter()

class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LogEntry:
    def __init__(self, message: str, level: LogLevel, timestamp: datetime, source: str):
        self.message = message
        self.level = level
        self.timestamp = timestamp
        self.source = source

def generate_demo_logs(count: int = 50) -> List[LogEntry]:
    """Generate demo log entries. Replace with real DB queries in production."""
    levels = [LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]
    sources = ["crawler", "processor", "api", "database"]
    messages = [
        "Started processing URL",
        "Connection timeout",
        "Successfully scraped content",
        "Failed to parse HTML",
        "Database connection error",
        "Cache miss",
        "Rate limit exceeded",
        "Content processed successfully"
    ]
    
    now = datetime.now()
    logs = []
    
    for _ in range(count):
        level = random.choice(levels)
        timestamp = now - timedelta(
            minutes=random.randint(0, 60),
            seconds=random.randint(0, 60)
        )
        logs.append(LogEntry(
            message=random.choice(messages),
            level=level,
            timestamp=timestamp,
            source=random.choice(sources)
        ))
    
    return sorted(logs, key=lambda x: x.timestamp, reverse=True)

@router.get("/api/v1/logs")
async def get_logs(
    level: Optional[LogLevel] = None,
    source: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    Get system logs with filtering and pagination.
    In production, replace with real database queries.
    """
    try:
        # Generate demo logs
        all_logs = generate_demo_logs(100)
        
        # Apply filters
        filtered_logs = all_logs
        if level:
            filtered_logs = [log for log in filtered_logs if log.level == level]
        if source:
            filtered_logs = [log for log in filtered_logs if log.source == source]
        
        # Calculate pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_logs = filtered_logs[start_idx:end_idx]
        
        return {
            "logs": [
                {
                    "message": log.message,
                    "level": log.level,
                    "timestamp": log.timestamp.isoformat(),
                    "source": log.source
                }
                for log in paginated_logs
            ],
            "total": len(filtered_logs),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(filtered_logs) + page_size - 1) // page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 