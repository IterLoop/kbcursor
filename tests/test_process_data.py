import os
import sys
import pytest
import logging
from datetime import datetime, UTC

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from scripts.process_data import process_with_assistant, setup_environment
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def env_setup():
    """Setup environment variables and verify configuration"""
    setup_environment()
    # Return commonly used environment variables
    return {
        'mongo_url': os.getenv('MONGO_DB_URL'),
        'db_name': os.getenv('MONGODB_DB_NAME2'),
        'openai_key': os.getenv('OPENAI_API_KEY'),
        'assistant_id': os.getenv('CLEANTEXT_ASSISTANT_ID')
    }

@pytest.fixture(scope="session")
def mongo_client(env_setup):
    """Create a MongoDB client for the test session"""
    client = MongoClient(env_setup['mongo_url'])
    yield client
    client.close()

@pytest.fixture(scope="session")
def openai_client(env_setup):
    """Create an OpenAI client for the test session"""
    return OpenAI(api_key=env_setup['openai_key'])

def test_environment_setup(env_setup):
    """Test that all required environment variables are set"""
    assert all(env_setup.values()), "Missing required environment variables"
    logger.info("Environment setup verified successfully")

def test_mongodb_connection(mongo_client, env_setup):
    """Test MongoDB connection and database access"""
    # Test connection
    mongo_client.admin.command('ping')
    
    # Access test database
    db = mongo_client[env_setup['db_name']]
    collections = db.list_collection_names()
    
    # Verify required collections exist
    assert 'raw_content' in collections, "raw_content collection not found"
    assert 'processed_content' in collections, "processed_content collection not found"
    logger.info(f"Available collections: {collections}")

def test_openai_connection(openai_client, env_setup):
    """Test OpenAI API connection and assistant access"""
    # Test basic API access
    models = openai_client.models.list()
    assert any(model.id.startswith('gpt') for model in models), "No GPT models available"
    
    # Test assistant access
    assistant = openai_client.beta.assistants.retrieve(env_setup['assistant_id'])
    assert assistant.id == env_setup['assistant_id'], "Assistant ID mismatch"
    logger.info(f"Successfully connected to OpenAI Assistant: {assistant.name}")

def test_process_single_document(mongo_client, openai_client, env_setup):
    """Test processing a single document from MongoDB"""
    db = mongo_client[env_setup['db_name']]
    raw_collection = db['raw_content']
    processed_collection = db['processed_content']
    
    # Find a document that hasn't been processed yet
    document = raw_collection.find_one({
        "text": {"$exists": True},
        "_id": {"$nin": processed_collection.distinct("original_id")}
    })
    
    if not document:
        pytest.skip("No unprocessed documents found in database")
    
    logger.info(f"Testing document processing for URL: {document.get('url', 'Unknown URL')}")
    text_content = document.get('text', '')
    assert text_content, "Document has no text content"
    
    # Process the document
    processed_result = process_with_assistant(openai_client, text_content)
    assert processed_result, "Processing returned no result"
    assert isinstance(processed_result, dict), "Result is not a dictionary"
    
    # Verify required fields in processed result
    required_fields = ['title', 'key_points', 'body_text']
    for field in required_fields:
        assert field in processed_result, f"Missing required field: {field}"
    
    # Update MongoDB
    update_result = processed_collection.insert_one({
        "original_id": document['_id'],
        "processed_result": processed_result,
        "processed_at": datetime.now(UTC)
    })
    assert update_result.inserted_id, "Failed to insert document in MongoDB"
    
    # Verify update
    updated_doc = processed_collection.find_one({"original_id": document['_id']})
    assert updated_doc is not None, "Processed document not found"
    logger.info("Document processing and storage verified successfully")


def test_data_pipeline_integrity(mongo_client, openai_client, env_setup):
    """Test the entire data processing pipeline"""
    db = mongo_client[env_setup['db_name']]
    raw_collection = db['raw_content']
    processed_collection = db['processed_content']
    
    # Get a sample of unprocessed documents
    processed_ids = set(processed_collection.distinct("original_id"))
    unprocessed_docs = list(raw_collection.find({
        "text": {"$exists": True},
        "_id": {"$nin": list(processed_ids)}
    }).limit(3))
    
    if not unprocessed_docs:
        pytest.skip("No unprocessed documents found for pipeline test")
    
    successful_processes = 0
    for doc in unprocessed_docs:
        try:
            # Process document
            text_content = doc.get('text', '')
            # Handle case where text might be a dict or list
            if isinstance(text_content, (dict, list)):
                if isinstance(text_content, dict):
                    text_content = text_content.get('content', '')
                else:
                    text_content = ' '.join(str(item) for item in text_content)
            
            if not text_content or not isinstance(text_content, str):
                logger.warning(f"Skipping document {doc['_id']}: Invalid text content")
                continue
                
            processed_result = process_with_assistant(openai_client, text_content)
            
            # Insert into processed_content collection
            insert_result = processed_collection.insert_one({
                "original_id": doc['_id'],
                "processed_result": processed_result,
                "processed_at": datetime.now(UTC),
                "source_url": doc.get('url', ''),  # Adding source URL for reference
                "content_hash": doc.get('content_hash', '')  # Adding content hash for tracking
            })
            
            if insert_result.inserted_id:
                successful_processes += 1
                logger.info(f"Successfully processed document {doc['_id']}")
                
        except Exception as e:
            logger.error(f"Error processing document {doc['_id']}: {str(e)}")
            continue
    
    # Only calculate success rate if we actually processed documents
    if len(unprocessed_docs) > 0:
        success_rate = successful_processes / len(unprocessed_docs)
        assert success_rate >= 0.66, f"Pipeline success rate too low: {success_rate:.2%}"
    else:
        logger.warning("No documents were processed")

if __name__ == "__main__":
    # For manual test execution
    pytest.main([__file__, "-v"])