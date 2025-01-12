"""MongoDB interface for the ghostwriter application."""

import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any, Union
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.results import InsertOneResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDB:
    """MongoDB database interface."""
    
    def __init__(self, mongo_url: str, db_name: str = "ghostwriter"):
        """Initialize MongoDB connection.
        
        Args:
            mongo_url: MongoDB connection URL
            db_name: Name of the database to use
        """
        try:
            self.client = MongoClient(mongo_url)
            self.db: Database = self.client[db_name]
            self._create_collections()
            self._create_indexes()
            logger.info(f"Successfully connected to MongoDB database: {db_name}")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            raise
    
    def _create_collections(self) -> None:
        """Create required collections if they don't exist."""
        collections = ["raw_content", "processed_content", "url_tracking"]
        for collection in collections:
            if collection not in self.db.list_collection_names():
                self.db.create_collection(collection)
    
    def _create_indexes(self) -> None:
        """Create required indexes."""
        try:
            # Raw content indexes
            self.db.raw_content.create_index([("url", ASCENDING)], unique=True)
            self.db.raw_content.create_index([("content_hash", ASCENDING)])
            
            # Processed content indexes
            self.db.processed_content.create_index([("original_id", ASCENDING)])
            self.db.processed_content.create_index([("processed_date", ASCENDING)])
            
            # URL tracking indexes
            self.db.url_tracking.create_index([("url", ASCENDING)], unique=True)
            self.db.url_tracking.create_index([("last_crawl", ASCENDING)])
            
            logger.info("Successfully created MongoDB indexes")
        except Exception as e:
            logger.error(f"Error creating indexes: {str(e)}")
            raise
        
    def store_raw_content(self, content: Dict[str, Any]) -> Optional[str]:
        """Store raw content in the database.
        
        Args:
            content: Dictionary containing the raw content
            
        Returns:
            ID of the inserted document or None if duplicate
        """
        try:
            # Check for required fields
            required_fields = ['url', 'title', 'text', 'metadata', 'content_hash']
            if not all(field in content for field in required_fields):
                logger.error("Missing required fields in content")
                return None
            
            # Check for duplicate URL
            if self.db.raw_content.find_one({"url": content["url"]}):
                logger.info(f"Duplicate URL found: {content['url']}")
                return None
            
            # Check for duplicate content hash
            if self.db.raw_content.find_one({"content_hash": content["content_hash"]}):
                logger.info(f"Duplicate content hash found: {content['content_hash']}")
                return None
                
            # Insert content
            result: InsertOneResult = self.db.raw_content.insert_one(content)
            
            # Update URL tracking
            self._update_url_tracking(content["url"])
            
            logger.info(f"Successfully stored raw content with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error storing raw content: {str(e)}")
            return None
            
    def store_processed_content(self, content: Dict[str, Any]) -> Optional[str]:
        """Store processed content in the database.
        
        Args:
            content: Dictionary containing the processed content
            
        Returns:
            ID of the inserted document or None if error
        """
        try:
            # Check for required fields
            required_fields = ['text', 'summary', 'processed_date']
            if not all(field in content for field in required_fields):
                logger.error("Missing required fields in processed content")
                return None
            
            # Insert content
            result: InsertOneResult = self.db.processed_content.insert_one(content)
            logger.info(f"Successfully stored processed content with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error storing processed content: {str(e)}")
            return None
            
    def export_processed_content(self) -> List[Dict[str, Any]]:
        """Export all processed content.
        
        Returns:
            List of processed content documents
        """
        try:
            cursor = self.db.processed_content.find({})
            return list(cursor)
        except Exception as e:
            logger.error(f"Error exporting processed content: {str(e)}")
            return []
            
    def _update_url_tracking(self, url: str) -> None:
        """Update URL tracking information.
        
        Args:
            url: URL to update tracking for
        """
        try:
            self.db.url_tracking.update_one(
                {"url": url},
                {
                    "$set": {
                        "last_crawl": datetime.now(UTC).isoformat(),
                        "crawl_count": 1
                    },
                    "$setOnInsert": {"first_crawl": datetime.now(UTC).isoformat()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating URL tracking: {str(e)}")
    
    def get_reliable_urls(self, min_crawls: int = 3) -> List[str]:
        """Get list of reliable URLs that have been successfully crawled multiple times.
        
        Args:
            min_crawls: Minimum number of successful crawls required
            
        Returns:
            List of reliable URLs
        """
        try:
            cursor = self.db.url_tracking.find(
                {"crawl_count": {"$gte": min_crawls}},
                {"url": 1}
            )
            return [doc["url"] for doc in cursor]
        except Exception as e:
            logger.error(f"Error getting reliable URLs: {str(e)}")
            return []
    
    def clear_test_data(self) -> None:
        """Clear all test data from the database."""
        try:
            self.db.raw_content.delete_many({})
            self.db.processed_content.delete_many({})
            self.db.url_tracking.delete_many({})
            logger.info("Successfully cleared test data")
        except Exception as e:
            logger.error(f"Error clearing test data: {str(e)}")