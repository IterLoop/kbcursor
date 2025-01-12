from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
import os
import logging
from datetime import datetime, UTC
from bson import ObjectId
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder for MongoDB ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

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
        
        # Convert cursor to list and serialize ObjectIds
        documents = json.loads(
            json.dumps(list(cursor), cls=MongoJSONEncoder)
        )
        
        logger.info(f"Returning {len(documents)} documents from {collection.name}")
        logger.info(f"Sample document: {documents[0] if documents else 'No documents'}")
            
        return {
            "total": total_docs,
            "page": page,
            "limit": limit,
            "documents": documents
        }
        
    except Exception as e:
        logger.error(f"Error in get_content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/data/search")
async def search_content(
    q: str,
    data_type: str = Query("raw", regex="^(raw|processed)$")
):
    try:
        # Select collection based on data_type
        collection = db['raw_content'] if data_type == "raw" else db['processed_content']
        
        # Build search query
        search_query = {
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"url": {"$regex": q, "$options": "i"}},
                {"text": {"$regex": q, "$options": "i"}}
            ]
        }
        
        logger.info(f"Search query: {search_query}")
        
        # Get search results with only required fields
        cursor = collection.find(
            search_query,
            {
                "_id": 1,
                "title": 1,
                "url": 1,
                "crawl_time": 1, 
                "status": 1
            }
        ).limit(10)
        
        # Convert cursor to list and serialize ObjectIds
        documents = json.loads(
            json.dumps(list(cursor), cls=MongoJSONEncoder)
        )
        
        logger.info(f"Found {len(documents)} documents matching search query")
            
        return {"documents": documents}
        
    except Exception as e:
        logger.error(f"Error in search_content: {str(e)}")
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

@app.post("/api/v1/data/rescrape")
async def rescrape_url(url_data: dict):
    try:
        # Find document in raw_content
        doc = db['raw_content'].find_one({"url": url_data["url"]})
        if not doc:
            raise HTTPException(status_code=404, detail="URL not found")
            
        # Update processing_status
        db['raw_content'].update_one(
            {"url": url_data["url"]},
            {"$set": {"processing_status": "queued"}}
        )
        
        # Initialize crawler and trigger rescrape
        from scripts.crawlers.multi_crawler import MultiCrawler
        crawler = MultiCrawler(
            apify_api_key=os.getenv('APIFY_API_KEY'),
            mongodb_url=os.getenv('MONGO_DB_URL'),
            serp_db_name=os.getenv('MONGODB_DB_NAME1'),
            crawl_db_name='content_data'
        )
        crawler.crawl_url(url_data["url"])
        
        return {"message": f"URL {url_data['url']} queued for rescraping"}
        
    except Exception as e:
        logger.error(f"Error in rescrape_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 