"""Script to update cleaned data with metadata from raw content."""
import os
from typing import Dict, Any
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_url(url: str) -> str:
    """Normalize URL for consistent comparison."""
    if not url:
        return url
    
    # Parse URL
    parsed = urlparse(url)
    
    # Normalize to https if no protocol specified
    scheme = parsed.scheme or 'https'
    
    # Remove trailing slashes and normalize to lowercase
    path = parsed.path.rstrip('/')
    netloc = parsed.netloc.lower()
    
    # Reconstruct URL with normalized components
    normalized = urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        ''  # Remove fragments
    ))
    
    return normalized

def update_cleaned_data_with_metatags():
    """Update cleaned data documents with metadata from raw content."""
    # Load environment variables
    load_dotenv(dotenv_path='secrets/.env')
    
    # Connect to MongoDB
    mongo_url = os.getenv('MONGO_DB_URL')
    if not mongo_url:
        raise ValueError("MONGO_DB_URL not found in environment variables")
    
    client = MongoClient(mongo_url)
    
    try:
        # Get database references with fallbacks
        cleaned_db_name = os.getenv('MONGODB_DB_NAME2', 'content_data')
        cleaned_db = client[cleaned_db_name]
        
        logger.info(f"Connected to database: {cleaned_db_name}")
        
        # List collections
        logger.info("\nAvailable collections in database:")
        for collection in cleaned_db.list_collection_names():
            logger.info(f"- {collection}")
        
        # Get collection references
        raw_collection = cleaned_db['raw_content']
        processed_collection = cleaned_db['processed_content']
        
        # Get total documents to update
        total_docs = processed_collection.count_documents({})
        logger.info(f"Found {total_docs} documents in processed content collection")
        
        # Counter for updated documents
        updated_count = 0
        skipped_count = 0
        
        # First, let's see what URLs we have in raw content
        raw_urls = set()
        for doc in raw_collection.find({}, {'url': 1}):
            if url := doc.get('url'):
                raw_urls.add(normalize_url(url))
        
        logger.info(f"Found {len(raw_urls)} URLs in raw content")
        logger.info("Sample of raw content URLs:")
        for url in list(raw_urls)[:5]:
            logger.info(f"- {url}")
        
        # Process each document in processed content
        for doc in processed_collection.find({}):
            original_url = doc.get('url')
            if not original_url:
                logger.warning(f"Skipping document {doc['_id']}: No URL found")
                skipped_count += 1
                continue
            
            # Normalize the URL
            normalized_url = normalize_url(original_url)
            logger.info(f"Processing URL: {original_url}")
            logger.info(f"Normalized to: {normalized_url}")
            
            # Find matching document in raw content
            raw_doc = raw_collection.find_one({
                'url': {
                    '$in': [
                        normalized_url,
                        normalized_url + '/',
                        original_url
                    ]
                }
            })
            
            if not raw_doc:
                logger.warning(f"No matching raw content found for URL: {original_url}")
                logger.warning(f"Normalized URL was: {normalized_url}")
                skipped_count += 1
                continue
            
            # Get metadata from raw content
            metadata = raw_doc.get('metadata', {})
            if not metadata:
                logger.warning(f"No metadata found for URL: {original_url}")
                skipped_count += 1
                continue
            
            # Update the processed content document with metadata
            result = processed_collection.update_one(
                {'_id': doc['_id']},
                {'$set': {'metadata': metadata}}
            )
            
            if result.modified_count > 0:
                updated_count += 1
                logger.info(f"Successfully updated document for URL: {original_url}")
                if updated_count % 100 == 0:
                    logger.info(f"Updated {updated_count}/{total_docs} documents")
            else:
                skipped_count += 1
                logger.warning(f"Failed to update document for URL: {original_url}")
        
        logger.info(f"Update complete. Updated: {updated_count}, Skipped: {skipped_count}")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise
    
    finally:
        client.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    update_cleaned_data_with_metatags() 