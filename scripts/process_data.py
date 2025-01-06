import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from openai import OpenAI
from pymongo import MongoClient
import time
import json
from config import MONGO_DB_URL, CONTENT_DB, RAW_CONTENT_COLLECTION, PROCESSED_CONTENT_COLLECTION
from tools.mongo import MongoValidator, RAW_CONTENT_SCHEMA, PROCESSED_CONTENT_SCHEMA
from datetime import datetime, UTC

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables and verify configuration"""
    # Get the project root directory
    ROOT_DIR = Path(__file__).parent.parent
    
    # Load environment variables
    env_path = ROOT_DIR / 'secrets' / '.env'
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found at {env_path}")
    
    load_dotenv(env_path)
    
    # Verify required environment variables
    required_vars = [
        'MONGO_DB_URL',
        'MONGODB_DB_NAME1',
        'MONGODB_DB_NAME2',
        'OPENAI_API_KEY',
        'CLEANTEXT_ASSISTANT_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def process_with_assistant(client, text_data=None, url=None, process_all=False):
    """Process text data using OpenAI Assistant and store results in MongoDB.
    If process_all is True, it will process all unprocessed documents in the database."""
    
    if process_all:
        try:
            # Initialize MongoDB client
            mongo_client = MongoClient(MONGO_DB_URL)
            content_db = mongo_client[CONTENT_DB]
            raw_content = content_db[RAW_CONTENT_COLLECTION]
            processed_content = content_db[PROCESSED_CONTENT_COLLECTION]
            
            # Find documents that haven't been processed yet
            documents = raw_content.find({
                "status": "success",
                "url": {
                    "$nin": [
                        doc["url"] 
                        for doc in processed_content.find({}, {"url": 1})
                    ]
                }
            })
            
            processed_count = 0
            failed_count = 0
            
            for doc in documents:
                logger.info(f"Processing document for URL: {doc.get('url', 'Unknown URL')}")
                
                text_content = doc.get('text', '')
                logger.info(f"Document text length: {len(text_content)} characters")
                
                if not text_content:
                    logger.warning(f"No text content found for document {doc['_id']}")
                    failed_count += 1
                    continue
                
                try:
                    # Process the document
                    processed_data = process_with_assistant(client, text_content, doc.get('url'))
                    
                    # Add metadata
                    current_time = datetime.now(UTC)
                    process_meta = {
                        "process_time": time.time(),
                        "content_type": "article",  # Default type
                        "word_count": len(processed_data.get("body_text", "").split()),
                        "processing_version": "1.0",  # Track version of processing logic
                        "last_updated": current_time,
                        "update_history": [
                            {
                                "timestamp": current_time,
                                "reason": "initial_processing"
                            }
                        ],
                        "status": "success"
                    }
                    
                    # Get source metadata from raw content
                    source_meta = doc.get("metadata", {}).get("source_meta", {})
                    
                    # Add metadata to processed data
                    processed_data["metadata"] = {
                        "source_meta": source_meta,
                        "process_meta": process_meta
                    }
                    
                    # Validate processed data against schema
                    processed_data = MongoValidator.prepare_for_mongodb(processed_data, PROCESSED_CONTENT_SCHEMA)
                    
                    # Store processed data
                    processed_content.update_one(
                        {"url": doc.get('url')},
                        {"$set": processed_data},
                        upsert=True
                    )
                    
                    processed_count += 1
                    logger.info(f"Successfully processed document for URL: {doc.get('url')}")
                except Exception as e:
                    logger.error(f"Error processing document {doc['_id']}: {e}")
                    # Record failure in metadata
                    try:
                        current_time = datetime.now(UTC)
                        process_meta = {
                            "process_time": time.time(),
                            "content_type": None,
                            "word_count": 0,
                            "processing_version": "1.0",
                            "last_updated": current_time,
                            "update_history": [
                                {
                                    "timestamp": current_time,
                                    "reason": f"processing_failed: {str(e)}"
                                }
                            ],
                            "status": "failed"
                        }
                        
                        failure_doc = {
                            "url": doc.get('url'),
                            "metadata": {
                                "source_meta": doc.get("metadata", {}).get("source_meta", {}),
                                "process_meta": process_meta
                            },
                            "status": "failed"
                        }
                        
                        processed_content.update_one(
                            {"url": doc.get('url')},
                            {"$set": failure_doc},
                            upsert=True
                        )
                    except Exception as inner_e:
                        logger.error(f"Error recording failure metadata: {inner_e}")
                    
                    failed_count += 1
            
            logger.info("\n=== Processing Summary ===")
            logger.info(f"Total documents processed: {processed_count}")
            logger.info(f"Failed documents: {failed_count}")
            logger.info("======================")
            
            return processed_count, failed_count
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise
            
    else:
        # Process single document
        if text_data is None:
            raise TypeError("Input text cannot be None when not in batch mode")
        if not text_data:
            raise ValueError("Input text cannot be empty when not in batch mode")

        # Use tokens instead of characters for more accurate chunking
        MAX_TOKENS = 3000  # Conservative limit for GPT-3.5
        CHUNK_OVERLAP = 500  # Tokens of overlap between chunks
        
        logger.info(f"Total input text length: {len(text_data)} characters")
        
        # Improved chunking strategy with overlap
        def create_chunks(text, max_tokens, overlap):
            # Rough approximation: 1 token ≈ 4 characters
            char_length = max_tokens * 4
            overlap_chars = overlap * 4
            chunks = []
            start = 0
            
            while start < len(text):
                end = start + char_length
                
                # If not the first chunk, include overlap from previous chunk
                if start > 0:
                    start = start - overlap_chars
                
                # If not the last chunk, try to break at a sentence
                if end < len(text):
                    # Look for sentence boundaries in the last 100 characters of the chunk
                    search_area = text[end-100:end]
                    sentences = ['. ', '? ', '! ']
                    
                    # Find the last sentence boundary in the search area
                    last_boundary = -1
                    for sep in sentences:
                        pos = search_area.rfind(sep)
                        if pos > last_boundary:
                            last_boundary = pos
                    
                    if last_boundary != -1:
                        end = end - (100 - last_boundary)
                
                chunks.append(text[start:end])
                start = end
            
            return chunks
        
        # Create chunks with improved strategy
        text_chunks = create_chunks(text_data, MAX_TOKENS, CHUNK_OVERLAP)
        logger.info(f"Split into {len(text_chunks)} chunks with overlap")
        
        thread = client.beta.threads.create()
        final_responses = []
        
        for chunk_num, chunk in enumerate(text_chunks, 1):
            logger.info(f"Processing chunk {chunk_num}/{len(text_chunks)}")
            
            # Enhanced prompt for better context handling
            message_content = f"""You are a data extraction assistant. Analyze the following text{' (continuation)' if chunk_num > 1 else ''} and extract structured information.
            
            {'If this is a continuation, update or complement the previous extraction as needed.' if chunk_num > 1 else 'Create a new structured extraction.'}
            
            Guidelines:
            - Maintain consistency across chunks
            - Avoid duplicating information from previous chunks
            - For continuing chunks, focus on new information
            
            JSON Output Format:
            {{
                "title": "string",
                "subtitle": "string or null",
                "author": "string or null",
                "published_date": "string or null",
                "key_points": ["array of strings"],
                "key_statistics": ["array of strings"],
                "notable_quotes": ["array of strings"],
                "source": "string or null",
                "category_tags": ["array of strings"],
                "body_text": "string enclosed with START OF BODY TEXT and END OF BODY TEXT markers",
                "additional_fields": {{
                    "key": "value pairs for any extra relevant information"
                }}
            }}

            Text chunk {chunk_num}/{len(text_chunks)}:
            {chunk}"""
            
            # Create message and run assistant
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_content
            )
            
            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=os.getenv('CLEANTEXT_ASSISTANT_ID')
            )
            
            if run.status == 'completed':
                messages = client.beta.threads.messages.list(thread_id=thread.id)
                assistant_response = next(msg for msg in messages if msg.role == "assistant")
                response_text = assistant_response.content[0].text.value
                final_responses.append(response_text)
                logger.info(f"Chunk {chunk_num} processed successfully")
            else:
                raise Exception(f"Assistant run failed with status: {run.status}")
        
        # Improved response merging
        def merge_responses(responses):
            merged_data = {
                "title": None,
                "subtitle": None,
                "author": None,
                "published_date": None,
                "key_points": set(),
                "key_statistics": set(),
                "notable_quotes": set(),
                "source": None,
                "category_tags": set(),
                "body_text": [],
                "additional_fields": {}
            }
            
            for response in responses:
                try:
                    data = json.loads(response)
                    # Merge scalar fields (take first non-null value)
                    for field in ["title", "subtitle", "author", "published_date", "source"]:
                        if merged_data[field] is None and data.get(field):
                            merged_data[field] = data[field]
                    
                    # Merge array fields (using sets to avoid duplicates)
                    for field in ["key_points", "key_statistics", "notable_quotes", "category_tags"]:
                        if data.get(field):
                            merged_data[field].update(data[field])
                    
                    # Concatenate body text
                    if data.get("body_text"):
                        merged_data["body_text"].append(data["body_text"])
                    
                    # Merge additional fields
                    if data.get("additional_fields"):
                        merged_data["additional_fields"].update(data["additional_fields"])
                
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response during merging: {e}")
                    continue
            
            # Convert sets back to lists
            for field in ["key_points", "key_statistics", "notable_quotes", "category_tags"]:
                merged_data[field] = list(merged_data[field])
            
            # Join body text parts
            merged_data["body_text"] = " ".join(merged_data["body_text"])
            
            return merged_data
        
        # Process chunks and get final result
        processed_data = None
        if len(final_responses) > 1:
            logger.info("Merging multiple chunk responses")
            processed_data = merge_responses(final_responses)
        else:
            processed_data = json.loads(final_responses[0])
        
        # Store results in MongoDB if URL is provided
        if url:
            try:
                # Initialize MongoDB client
                mongo_client = MongoClient(os.getenv('MONGO_DB_URL'))
                content_db = mongo_client[os.getenv('MONGODB_DB_NAME2')]
                processed_content = content_db['processed_content']
                
                # Create document for processed_content collection
                document = {
                    "url": url,
                    "title": processed_data.get("title"),
                    "subtitle": processed_data.get("subtitle"),
                    "author": processed_data.get("author"),
                    "published_date": processed_data.get("published_date"),
                    "key_points": processed_data.get("key_points", []),
                    "key_statistics": processed_data.get("key_statistics", []),
                    "notable_quotes": processed_data.get("notable_quotes", []),
                    "source": processed_data.get("source"),
                    "category_tags": processed_data.get("category_tags", []),
                    "body_text": processed_data.get("body_text"),
                    "additional_fields": processed_data.get("additional_fields", {}),
                    "process_time": time.time(),
                    "content_type": "article"  # Default type, can be customized based on content
                }
                
                # Insert into processed_content collection
                result = processed_content.insert_one(document)
                
                logger.info(f"Successfully stored processed data with ID: {result.inserted_id}")
                
                # Verify the insertion
                stored_doc = processed_content.find_one({"_id": result.inserted_id})
                if not stored_doc:
                    logger.warning("Document verification failed - processed document not found")
                    
            except Exception as e:
                logger.error(f"Failed to store processed data in MongoDB: {e}")
                raise
        
        return processed_data

def main():
    """Main function to process all unprocessed data from MongoDB"""
    try:
        # Setup environment
        setup_environment()
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Process all unprocessed documents
        process_with_assistant(openai_client, process_all=True)
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Program completed") 