import os
import logging
from openai import OpenAI
from pymongo import MongoClient
from scripts.process_data import process_with_assistant, setup_environment

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_unprocessed_content():
    """
    Controller function that processes content for URLs that exist in raw_content
    but are missing from processed_content collection.
    """
    try:
        # Setup environment variables
        setup_environment()
        
        # Initialize MongoDB client
        mongo_client = MongoClient(os.getenv('MONGO_DB_URL'))
        db = mongo_client[os.getenv('MONGODB_DB_NAME1')]
        raw_collection = db['raw_content']
        processed_collection = db['processed_content']
        
        # Get all processed URLs
        processed_urls = set(doc['url'] for doc in processed_collection.find({}, {"url": 1}))
        logger.info(f"Found {len(processed_urls)} already processed URLs")
        
        # Find documents in raw_content where URL is not in processed_content
        pipeline = [
            {
                "$match": {
                    "url": {"$nin": list(processed_urls)},
                    "text": {"$exists": True, "$ne": ""}
                }
            }
        ]
        unprocessed_docs = list(raw_collection.aggregate(pipeline))
        total_to_process = len(unprocessed_docs)
        logger.info(f"Found {total_to_process} unprocessed documents in raw_content")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        processed_count = 0
        failed_count = 0
        
        # Process each unprocessed document
        for i, doc in enumerate(unprocessed_docs, 1):
            url = doc.get('url')
            text = doc.get('text')
            
            if not url or not text:
                logger.warning(f"Skipping document with missing url or text: {doc.get('_id')}")
                continue
                
            try:
                logger.info(f"Processing document {i}/{total_to_process}")
                logger.info(f"URL: {url}")
                logger.info(f"Text length: {len(text)} characters")
                
                # Verify URL is still unprocessed (in case of concurrent processing)
                if processed_collection.find_one({"url": url}):
                    logger.info(f"URL {url} was processed by another process, skipping")
                    continue
                
                # Process the document using process_data's function
                process_with_assistant(
                    client=client,
                    text_data=text,
                    url=url,
                    process_all=False  # Process single document mode
                )
                
                processed_count += 1
                logger.info(f"Successfully processed URL: {url}")
                logger.info(f"Progress: {processed_count + failed_count}/{total_to_process} documents processed")
                
            except Exception as e:
                logger.error(f"Failed to process URL {url}: {e}")
                failed_count += 1
                logger.info(f"Progress: {processed_count + failed_count}/{total_to_process} documents processed")
        
        mongo_client.close()
        return {
            "status": "success",
            "processed_count": processed_count,
            "failed_count": failed_count,
            "message": f"Completed processing {processed_count + failed_count}/{total_to_process} documents ({processed_count} successful, {failed_count} failed)"
        }
        
    except Exception as e:
        logger.error(f"Error in process_content controller: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    result = process_unprocessed_content()
    logger.info(f"Processing complete: {result}")
