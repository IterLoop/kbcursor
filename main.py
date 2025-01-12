from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any
from pymongo import MongoClient
import os
import logging
from bson import ObjectId, json_util
import json
from datetime import datetime
from pydantic import BaseModel
from scripts.api.search_terms_generator import SearchTermGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = MongoClient(os.getenv('MONGO_DB_URL', 'mongodb://localhost:27017'))
db = client['content_data']

# Add logging to verify database connection
logger.info(f"Connected to database: {db.name}")
logger.info(f"Available collections: {db.list_collection_names()}")
logger.info(f"Raw content count: {db['raw_content'].count_documents({})}")
logger.info(f"Processed content count: {db['processed_content'].count_documents({})}")

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def serialize_mongodb(data: Any) -> Any:
    """Serialize MongoDB data including ObjectId and datetime."""
    return json.loads(json.dumps(data, cls=MongoJSONEncoder))

# Add Pydantic model for date range
class DateRange(BaseModel):
    start: str
    end: str

# Add Pydantic model for article request
class ArticleRequest(BaseModel):
    outline: str
    audience: str
    writing_style: str
    imagination_level: int
    research_level: int
    date_range: DateRange

@app.get("/api/v1/data/content")
async def get_content(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    data_type: str = Query("raw", regex="^(raw|processed)$")
):
    try:
        # Select collection based on data_type
        collection = db['raw_content'] if data_type == "raw" else db['processed_content']
        
        # Log collection being queried
        logger.info(f"Querying collection: {collection.name}")
        
        # Count total documents
        total_docs = collection.count_documents({})
        logger.info(f"Total documents in {collection.name}: {total_docs}")
        
        # Calculate skip
        skip = (page - 1) * limit
        
        # Get paginated results with only required fields
        cursor = collection.find(
            {},
            {
                "_id": 1,
                "title": 1,
                "url": 1, 
                "crawl_time": 1,
                "status": 1
            }
        ).skip(skip).limit(limit)
        
        # Convert cursor to list and serialize
        documents = list(cursor)
        serialized_docs = serialize_mongodb(documents)
        
        logger.info(f"Returning {len(serialized_docs)} documents from {collection.name}")
        if serialized_docs:
            logger.info(f"Sample document: {serialized_docs[0]}")
            
        return {
            "total": total_docs,
            "page": page,
            "limit": limit,
            "documents": serialized_docs
        }
        
    except Exception as e:
        logger.error(f"Error in get_content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/data/collections")
async def get_collections():
    try:
        collections = {
            "raw_content": db['raw_content'].count_documents({}),
            "processed_content": db['processed_content'].count_documents({})
        }
        logger.info(f"Collection counts: {collections}")
        return collections
        
    except Exception as e:
        logger.error(f"Error in get_collections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/articles/generate")
async def generate_article_prompt(request: ArticleRequest):
    try:
        # Create a new document with the request data
        article_request = {
            **request.dict(),
            "created_at": datetime.utcnow(),
            "status": "pending"
        }
        
        # Insert into article_requests collection
        result = db['article_requests'].insert_one(article_request)
        
        # Generate agent prompt (placeholder for now)
        agent_prompt = f"""Search for information about {request.outline}
Audience: {request.audience}
Style: {request.writing_style}
Imagination Level: {request.imagination_level}
Research Level: {request.research_level}
Date Range: {request.date_range.start} to {request.date_range.end}"""

        # Generate search terms (placeholder for now)
        search_terms = [word for word in request.outline.split() if len(word) > 3]
        
        response = {
            "request_id": str(result.inserted_id),
            "agent_prompt": agent_prompt,
            "search_terms": search_terms,
            "date_range": {
                "start": request.date_range.start,
                "end": request.date_range.end
            }
        }
        
        logger.info(f"Created article request: {response['request_id']}")
        return serialize_mongodb(response)
        
    except Exception as e:
        logger.error(f"Error in generate_article_prompt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/articles/generate_search_terms")
async def generate_search_terms(article_request: ArticleRequest):
    try:
        generator = SearchTermGenerator()
        search_terms = generator.generate_search_terms(
            topic=article_request.outline,
            params={
                "audience": article_request.audience,
                "writing_style": article_request.writing_style,
                "imagination_level": article_request.imagination_level,
                "research_level": article_request.research_level,
                "date_from": article_request.date_range.start,
                "date_to": article_request.date_range.end
            }
        )
        
        return {
            "search_terms": search_terms,
            "date_range": {
                "start": article_request.date_range.start,
                "end": article_request.date_range.end
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating search terms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
