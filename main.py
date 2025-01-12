import os
from pathlib import Path
from scripts.serp import fetch_search_results
from scripts.crawlers.multi_crawler import MultiCrawler
from scripts.process_data import process_with_assistant
from dotenv import load_dotenv
import json
import logging
from openai import OpenAI
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tools.mongo import MongoDB
from typing import Optional, List
from pydantic import BaseModel
from bson import ObjectId

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('search_runs.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MongoDB connection
try:
    mongo_client = MongoDB(os.getenv('MONGO_DB_URL', 'mongodb://localhost:27017'), 'ghostwriter')
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

class ContentResponse(BaseModel):
    _id: str
    url: str
    title: str
    date_crawled: str
    processing_status: str
    source: str

@app.get("/api/v1/data/content")
async def get_content(
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    source: Optional[str] = None
) -> List[ContentResponse]:
    try:
        skip = (page - 1) * limit
        query = {}
        if status:
            query["processing_status"] = status
        if source:
            query["source"] = source

        logger.info(f"MongoDB Query: {query}")
        
        # Get total count
        total_count = mongo_client.db.raw_content.count_documents(query)
        logger.info(f"Total documents matching query: {total_count}")

        cursor = mongo_client.db.raw_content.find(
            query,
            {
                "_id": 1,
                "url": 1,
                "title": 1,
                "date_crawled": 1,
                "processing_status": 1,
                "source": 1
            }
        ).skip(skip).limit(limit)

        content = []
        for doc in cursor:
            logger.info(f"Found document: {doc}")
            content.append(ContentResponse(
                _id=str(doc["_id"]),
                url=doc["url"],
                title=doc.get("title", "No title"),
                date_crawled=doc.get("date_crawled", datetime.now().isoformat()),
                processing_status=doc.get("processing_status", "raw"),
                source=doc.get("source", "web")
            ))
        
        logger.info(f"Returning {len(content)} documents")
        return content
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/data/content/{content_id}")
async def get_content_detail(content_id: str):
    try:
        # Convert string ID to ObjectId
        obj_id = ObjectId(content_id)
        
        # Get raw content
        raw_content = mongo_client.db.raw_content.find_one({"_id": obj_id})
        if not raw_content:
            raise HTTPException(status_code=404, detail="Content not found")
            
        # Get processed content if it exists
        processed_content = mongo_client.db.processed_content.find_one({"original_id": obj_id})
        
        # Convert ObjectId to string
        raw_content["_id"] = str(raw_content["_id"])
        if processed_content:
            processed_content["_id"] = str(processed_content["_id"])
        
        # Return the response with the exact structure expected by frontend
        return {
            "raw_content": raw_content,
            "processed_content": processed_content
        }
    except Exception as e:
        logger.error(f"Error fetching content detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/data/content/{content_id}/reprocess")
async def reprocess_content(content_id: str):
    try:
        content = mongo_client.db.raw_content.find_one({"_id": content_id})
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        # Update processing status
        mongo_client.db.raw_content.update_one(
            {"_id": content_id},
            {"$set": {"processing_status": "processing"}}
        )
        
        # TODO: Implement reprocessing logic
        return {"status": "processing"}
    except Exception as e:
        logger.error(f"Error reprocessing content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/data/pipeline/status")
async def get_pipeline_status():
    try:
        # Get all content being processed
        processing = mongo_client.db.raw_content.find(
            {"processing_status": "processing"},
            {"_id": 1, "url": 1, "progress": 1}
        ).limit(10)
        
        tasks = []
        for doc in processing:
            tasks.append({
                "task_id": str(doc["_id"]),
                "content_id": doc["url"],
                "task_type": "Processing",
                "progress": doc.get("progress", 0)
            })
        return tasks
    except Exception as e:
        logger.error(f"Error fetching pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def setup_environment():
    """Setup environment variables and verify configuration"""
    # Get the project root directory
    ROOT_DIR = Path(__file__).parent
    
    # Load environment variables
    env_path = ROOT_DIR / 'secrets' / '.env'
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found at {env_path}")
    
    load_dotenv(env_path)
    
    # Verify required environment variables
    required_vars = [
        'APIFY_API_KEY',
        'MONGO_DB_URL',
        'MONGODB_DB_NAME1',
        'MONGODB_DB_NAME2',
        'OPENAI_API_KEY',
        'CLEANTEXT_ASSISTANT_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def load_runlist() -> list:
    """Load the runlist from JSON file"""
    runlist_path = Path(__file__).parent / 'runlist.json'
    if not runlist_path.exists():
        raise FileNotFoundError(f"Runlist file not found at {runlist_path}")
    
    with open(runlist_path) as f:
        return json.load(f)

def search_and_crawl():
    """Main function to handle search and crawl operations"""
    try:
        # Setup environment
        setup_environment()
        ROOT_DIR = Path(__file__).parent
        
        # Add run start timestamp
        run_start_time = datetime.now()
        logger.info(f"Starting new run at {run_start_time}")
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize crawler
        crawler = MultiCrawler(
            mongodb_url=os.getenv('MONGO_DB_URL'),
            serp_db_name=os.getenv('MONGODB_DB_NAME1'),
            crawl_db_name=os.getenv('MONGODB_DB_NAME2'),
            proxy_file_path=str(ROOT_DIR / 'other' / 'proxies.txt'),
            apify_api_key=os.getenv('APIFY_API_KEY')
        )
        
        # Load runlist
        runlist = load_runlist()
        total_searches = len(runlist)
        
        for search_idx, search_item in enumerate(runlist, 1):
            search_term = search_item['search_term']
            results_count = search_item.get('results_count', 10)
            
            # Add search start timestamp
            search_start_time = datetime.now()
            logger.info(f"\n=== Search Run {search_idx}/{total_searches} Started at {search_start_time} ===")
            logger.info(f"Search term: '{search_term}'")
            logger.info(f"Results count: {results_count}")
            
            try:
                # Step 1: Fetch search results
                logger.info(f"Fetching search results for: '{search_term}'")
                search_results = fetch_search_results(search_term, results_count)
                
                # Step 2: Crawl URLs
                logger.info(f"Starting crawl for {len(search_results)} URLs")
                crawler.crawl_urls(search_results, search_term)
                
                # Step 3: Process crawled content
                logger.info("Processing crawled content with OpenAI Assistant")
                process_with_assistant(openai_client, process_all=True)
                
                # Log search completion
                search_end_time = datetime.now()
                search_duration = search_end_time - search_start_time
                logger.info(f"\n=== Search Run {search_idx} Completed ===")
                logger.info(f"Duration: {search_duration}")
                logger.info(f"URLs crawled: {len(search_results)}")
                logger.info(f"Successful crawls: {crawler.successful_crawls}")
                logger.info(f"Failed crawls: {crawler.failed_crawls}")
                logger.info("================================")
                
            except Exception as e:
                logger.error(f"Error processing search term '{search_term}': {e}")
                continue
        
        # Add run completion summary
        run_end_time = datetime.now()
        run_duration = run_end_time - run_start_time
        logger.info("\n=== Complete Run Summary ===")
        logger.info(f"Run start time: {run_start_time}")
        logger.info(f"Run end time: {run_end_time}")
        logger.info(f"Total duration: {run_duration}")
        logger.info(f"Total searches completed: {total_searches}")
        logger.info("============================")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    try:
        search_and_crawl()
    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Program completed")
