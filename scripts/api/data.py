from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import random  # For demo data

router = APIRouter()

class ContentMetadata(BaseModel):
    url: str
    title: str
    date_crawled: datetime
    processing_status: str
    source: str
    word_count: int
    
class ContentDetail(ContentMetadata):
    full_text: str
    summary: str
    tags: List[str]
    classifications: dict
    embedding_dimensions: int
    
class PipelineTask(BaseModel):
    task_id: str
    content_id: str
    task_type: str
    status: str
    progress: float
    estimated_completion: datetime

def generate_demo_content():
    statuses = ["processed", "raw", "processing", "failed"]
    sources = ["web", "pdf", "social", "news"]
    
    return {
        "url": f"https://example.com/article-{random.randint(1, 1000)}",
        "title": f"Sample Article {random.randint(1, 100)}",
        "date_crawled": datetime.now(),
        "processing_status": random.choice(statuses),
        "source": random.choice(sources),
        "word_count": random.randint(100, 5000)
    }

def generate_demo_detail():
    base = generate_demo_content()
    return {
        **base,
        "full_text": "This is a sample article full text...",
        "summary": "A brief summary of the article content...",
        "tags": ["technology", "ai", "web"],
        "classifications": {
            "category": "technology",
            "sentiment": "positive",
            "relevance": 0.85
        },
        "embedding_dimensions": 768
    }

@router.get("/content", response_model=List[ContentMetadata])
async def get_content(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    source: Optional[str] = None
):
    # Demo implementation - replace with actual MongoDB query
    start = (page - 1) * limit
    end = start + limit
    content = [generate_demo_content() for _ in range(limit)]
    
    if status:
        content = [c for c in content if c["processing_status"] == status]
    if source:
        content = [c for c in content if c["source"] == source]
    
    return content

@router.get("/content/{content_id}", response_model=ContentDetail)
async def get_content_detail(content_id: str):
    # Demo implementation - replace with actual MongoDB query
    return generate_demo_detail()

@router.post("/content/{content_id}/reprocess")
async def reprocess_content(content_id: str):
    # Demo implementation - replace with actual reprocessing logic
    return {"status": "success", "message": f"Content {content_id} queued for reprocessing"}

@router.get("/pipeline/status", response_model=List[PipelineTask])
async def get_pipeline_status():
    # Demo implementation - replace with actual pipeline status
    tasks = []
    for i in range(3):
        task = PipelineTask(
            task_id=f"task-{i}",
            content_id=f"content-{i}",
            task_type=random.choice(["summarize", "classify", "embed"]),
            status=random.choice(["queued", "processing", "completed"]),
            progress=random.random(),
            estimated_completion=datetime.now()
        )
        tasks.append(task)
    return tasks 