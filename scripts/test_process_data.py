from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from process_data import process_with_assistant
from openai import OpenAI
import logging
import json
import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_single_document():
    # Load environment variables
    load_dotenv('secrets/.env')
    
    # Initialize MongoDB client
    mongo_client = MongoClient(os.getenv('MONGO_DB_URL'))
    source_db = mongo_client[os.getenv('MONGODB_DB_NAME2')]
    
    # Initialize OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Get specific document
    doc_id = ObjectId('67784a7e3fb9c3cc2c128790')
    document = source_db['scraped_data'].find_one({"_id": doc_id})
    
    if document:
        logger.info(f"Found document with URL: {document.get('url', 'Unknown URL')}")
        text_content = document.get('text', '')
        
        if text_content:
            # Process with OpenAI Assistant
            processed_result = process_with_assistant(openai_client, text_content)
            logger.info("Processed Result:")
            print(processed_result)
            
            # Write back to MongoDB
            update_result = source_db['scraped_data'].update_one(
                {"_id": doc_id},
                {"$set": {"processed_result": processed_result}}
            )
            
            # Confirm the update
            if update_result.modified_count > 0:
                logger.info("Successfully updated document in MongoDB")
                
                # Verify the update by retrieving the document
                updated_doc = source_db['scraped_data'].find_one({"_id": doc_id})
                if updated_doc.get('processed_result'):
                    logger.info("Verification successful - processed_result found in document")
                    logger.info(f"Length of stored processed_result: {len(updated_doc['processed_result'])}")
                else:
                    logger.error("Verification failed - processed_result not found in document")
            else:
                logger.error("Failed to update document in MongoDB")
        else:
            logger.error("No text content found in document")
    else:
        logger.error(f"Document with ID {doc_id} not found")

if __name__ == "__main__":
    test_single_document() 