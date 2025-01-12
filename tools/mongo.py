"""MongoDB database operations and schema validation."""
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import logging
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Schema
SEARCH_SCHEMA = {
    "query_term": str,
    "timestamp": "datetime",
    "results": [
        {
            "url": str,
            "meta_tags": dict
        }
    ]
}

RAW_CONTENT_SCHEMA = {
    "url": str,
    "title": str,
    "text": str,
    "metadata": {
        "source_meta": dict,  # Original metadata from source
        "crawl_meta": {
            "method": str,
            "crawl_time": "datetime",
            "updated_at": "datetime",
            "content_hash": str,
            "word_count": int,
            "status": str,
            "attempts": int,
            "last_success": "datetime",
            "last_failure": "datetime",
            "failure_reason": str
        }
    },
    "method": str,
    "crawl_time": "datetime",
    "updated_at": "datetime",
    "word_count": int,
    "status": str,
    "content_hash": str
}

PROCESSED_CONTENT_SCHEMA = {
    "url": str,
    "title": str,
    "subtitle": str,
    "author": str,
    "published_date": str,
    "key_points": list,
    "key_statistics": list,
    "notable_quotes": list,
    "source": str,
    "category_tags": list,
    "body_text": str,
    "metadata": {
        "source_meta": dict,  # Original metadata from source
        "process_meta": {
            "process_time": float,
            "content_type": str,
            "word_count": int,
            "processing_version": str,
            "last_updated": "datetime",
            "update_history": list,  # List of update timestamps and reasons
            "status": str
        }
    },
    "additional_fields": dict,
    "process_time": float,
    "content_type": str
}

class MongoValidator:
    """Handles MongoDB data validation and sanitization."""
    
    @staticmethod
    def validate_type(value: Any, expected_type: Union[type, str]) -> bool:
        """Validate if a value matches the expected type."""
        if expected_type == "datetime":
            return isinstance(value, (datetime, str)) and bool(value)
        return isinstance(value, expected_type)

    @staticmethod
    def validate_schema(data: Dict[str, Any], schema: Dict[str, Any], path: str = "") -> List[str]:
        """
        Validate data against a schema and return list of validation errors.
        Returns empty list if validation passes.
        """
        errors = []
        
        for key, expected_type in schema.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check if required field exists
            if key not in data:
                errors.append(f"Missing required field: {current_path}")
                continue
                
            value = data[key]
            
            # Handle nested dictionaries
            if isinstance(expected_type, dict):
                if not isinstance(value, dict):
                    errors.append(f"Field {current_path} should be a dictionary")
                else:
                    errors.extend(MongoValidator.validate_schema(value, expected_type, current_path))
                continue
                
            # Handle lists of dictionaries
            if isinstance(expected_type, list):
                if not isinstance(value, list):
                    errors.append(f"Field {current_path} should be a list")
                else:
                    for i, item in enumerate(value):
                        if not isinstance(item, dict):
                            errors.append(f"Item {i} in {current_path} should be a dictionary")
                        else:
                            errors.extend(MongoValidator.validate_schema(item, expected_type[0], f"{current_path}[{i}]"))
                continue
                
            # Validate type
            if not MongoValidator.validate_type(value, expected_type):
                errors.append(f"Field {current_path} should be of type {expected_type.__name__}")
        
        return errors

    @staticmethod
    def sanitize_data(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize data to match schema. Handles missing or invalid fields by:
        - Adding missing required fields with default values
        - Converting types where possible
        - Removing fields not in schema
        """
        sanitized = {}
        
        for key, expected_type in schema.items():
            value = data.get(key)
            
            # Handle missing values
            if value is None:
                if expected_type == str:
                    sanitized[key] = ""
                elif expected_type == int:
                    sanitized[key] = 0
                elif expected_type == float:
                    sanitized[key] = 0.0
                elif expected_type == list:
                    sanitized[key] = []
                elif expected_type == dict:
                    sanitized[key] = {}
                elif expected_type == "datetime":
                    sanitized[key] = datetime.utcnow()
                continue
                
            # Handle type conversions
            try:
                if expected_type == str:
                    sanitized[key] = str(value)
                elif expected_type == int:
                    sanitized[key] = int(float(value))
                elif expected_type == float:
                    sanitized[key] = float(value)
                elif expected_type == list and not isinstance(value, list):
                    sanitized[key] = [value]
                elif expected_type == dict and not isinstance(value, dict):
                    sanitized[key] = {"value": value}
                elif expected_type == "datetime" and isinstance(value, str):
                    try:
                        sanitized[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        sanitized[key] = datetime.utcnow()
                else:
                    sanitized[key] = value
            except (ValueError, TypeError):
                # If conversion fails, use default value
                if expected_type == str:
                    sanitized[key] = str(value) if value is not None else ""
                elif expected_type in (int, float):
                    sanitized[key] = 0
                elif expected_type == list:
                    sanitized[key] = []
                elif expected_type == dict:
                    sanitized[key] = {}
                elif expected_type == "datetime":
                    sanitized[key] = datetime.utcnow()
        
        return sanitized

    @staticmethod
    def prepare_for_mongodb(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare data for MongoDB storage:
        1. Validate against schema
        2. Sanitize data if needed
        3. Return clean data ready for storage
        """
        # First validate
        errors = MongoValidator.validate_schema(data, schema)
        
        if errors:
            # Log validation errors
            logger.warning("Data validation errors:")
            for error in errors:
                logger.warning(f"- {error}")
            
            # Sanitize data
            logger.info("Attempting to sanitize data...")
            data = MongoValidator.sanitize_data(data, schema)
            
            # Validate again after sanitization
            errors = MongoValidator.validate_schema(data, schema)
            if errors:
                logger.error("Data still invalid after sanitization:")
                for error in errors:
                    logger.error(f"- {error}")
                raise ValueError("Data validation failed even after sanitization")
        
        return data

class MongoManager:
    """Manages MongoDB database operations."""
    
    def __init__(self):
        """Initialize MongoDB connection and setup databases."""
        self.client = MongoClient(os.getenv('MONGO_DB_URL'))
        self.search_db = self.client[os.getenv('MONGODB_DB_NAME1')]
        self.content_db = self.client[os.getenv('MONGODB_DB_NAME2')]
        self.validator = MongoValidator()
        
    def init_search_db(self):
        """Initialize search database with proper collections and indexes."""
        searches = self.search_db['searches']
        
        # Create indexes
        searches.create_index([("query_term", ASCENDING)], background=True)
        searches.create_index([("timestamp", ASCENDING)], background=True)
        searches.create_index([("results.url", ASCENDING)], background=True)
        
        logger.info(f"Initialized search database '{self.search_db.name}' with indexes")
        
    def init_content_db(self):
        """Initialize content database with proper collections and indexes."""
        # Create raw_content collection with indexes
        raw_content = self.content_db['raw_content']
        raw_content.create_index([("url", ASCENDING)], unique=True, background=True)
        raw_content.create_index([("crawl_time", ASCENDING)], background=True)
        raw_content.create_index([("content_hash", ASCENDING)], background=True)
        
        # Create processed_content collection with indexes
        processed_content = self.content_db['processed_content']
        processed_content.create_index([("url", ASCENDING)], background=True)
        processed_content.create_index([("process_time", ASCENDING)], background=True)
        processed_content.create_index([("content_type", ASCENDING)], background=True)
        
        logger.info(f"Initialized content database '{self.content_db.name}' with indexes")
        
    def verify_database_structure(self):
        """Verify that all collections and indexes are properly set up."""
        # Verify search database
        search_indexes = self.search_db['searches'].list_indexes()
        logger.info("\nSearch Database Indexes:")
        for idx in search_indexes:
            logger.info(f"- {idx['name']}: {idx['key']}")
        
        # Verify content database
        raw_indexes = self.content_db['raw_content'].list_indexes()
        logger.info("\nRaw Content Indexes:")
        for idx in raw_indexes:
            logger.info(f"- {idx['name']}: {idx['key']}")
        
        processed_indexes = self.content_db['processed_content'].list_indexes()
        logger.info("\nProcessed Content Indexes:")
        for idx in processed_indexes:
            logger.info(f"- {idx['name']}: {idx['key']}")
            
    def close(self):
        """Close MongoDB connection."""
        self.client.close()