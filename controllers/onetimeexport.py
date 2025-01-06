import logging
from pymongo import MongoClient
from pprint import pprint
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def confirm_action(message: str) -> bool:
    """Ask user for confirmation before proceeding"""
    response = input(f"\n{message} (yes/no): ").lower().strip()
    return response == 'yes'

def preview_data(data: Dict[str, Any], limit: int = 3) -> None:
    """Show preview of data to be migrated"""
    print("\nPreview of data (first 3 documents):")
    print("-" * 50)
    for i, doc in enumerate(data[:limit]):
        pprint(doc)
        if i < len(data[:limit]) - 1:
            print("-" * 30)
    print(f"\nTotal documents to migrate: {len(data)}")

def migrate_raw_content(source_url: str, dest_url: str):
    """
    Migrates data from MONGODB_DB_NAME2/processed_content to content_data/processed_content
    """
    try:
        # Connect to source database
        source_client = MongoClient(source_url)
        source_db = source_client['MONGODB_DB_NAME2']  # Hard coded database name
        source_collection = source_db['processed_content']
        
        # Get all data from source and remove _id field
        source_data = list(source_collection.find({}, {'_id': 0}))
        
        if not source_data:
            logger.info("No data found in source collection")
            return
            
        # Show preview and get confirmation
        preview_data(source_data)
        
        # Check for duplicate URLs in source data
        urls = [doc.get('url') for doc in source_data if 'url' in doc]
        duplicate_urls = set([url for url in urls if urls.count(url) > 1])
        if duplicate_urls:
            logger.warning(f"Found {len(duplicate_urls)} duplicate URLs in source data:")
            for url in list(duplicate_urls)[:5]:  # Show first 5 duplicates
                logger.warning(f"Duplicate URL: {url}")
            if not confirm_action("Continue despite duplicate URLs?"):
                logger.info("Migration cancelled by user")
                return
            
        # Connect to destination database
        dest_client = MongoClient(dest_url)
        dest_db = dest_client['content_data']
        dest_collection = dest_db['processed_content']
        
        # Drop existing URL index if it exists
        try:
            dest_collection.drop_index("url_1")
            logger.info("Dropped existing URL index")
        except:
            logger.info("No existing URL index to drop")
        
        # Create new URL index
        dest_collection.create_index([("url", 1)], unique=True, background=True)
        logger.info("Created new unique URL index")
        
        # Check for existing documents with same URLs
        existing_urls = set(dest_collection.distinct('url'))
        conflicting_urls = set(urls) & existing_urls
        if conflicting_urls:
            logger.warning(f"Found {len(conflicting_urls)} URLs that already exist in destination:")
            for url in list(conflicting_urls)[:5]:  # Show first 5 conflicts
                logger.warning(f"Conflicting URL: {url}")
            if not confirm_action("Do you want to skip existing URLs and continue?"):
                logger.info("Migration cancelled by user")
                return
            
            # Filter out documents with existing URLs
            source_data = [doc for doc in source_data if doc.get('url') not in existing_urls]
            logger.info(f"Will migrate {len(source_data)} documents (skipping existing URLs)")
        
        if not source_data:
            logger.info("No new documents to migrate after filtering")
            return
            
        # Insert data into destination
        dest_collection.insert_many(source_data)
        logger.info(f"Successfully migrated {len(source_data)} processed content documents")
        
        # Verify migration
        dest_count = dest_collection.count_documents({})
        logger.info(f"Verification: {dest_count} total documents in destination collection")
        
        if not confirm_action("Does the migration look correct? (no will trigger rollback)"):
            logger.info("Rolling back migration...")
            # Only delete the documents we just inserted
            urls_inserted = [doc.get('url') for doc in source_data]
            dest_collection.delete_many({"url": {"$in": urls_inserted}})
            logger.info("Rollback completed")
        
        source_client.close()
        dest_client.close()
            
    except Exception as e:
        logger.error(f"Error migrating processed content: {str(e)}")
        raise

# Example usage:
if __name__ == "__main__":
    # Local MongoDB connection strings
    SOURCE_MONGO_URL = "mongodb://localhost:27017"
    DEST_MONGO_URL = "mongodb://localhost:27017"
    
    migrate_raw_content(SOURCE_MONGO_URL, DEST_MONGO_URL)
