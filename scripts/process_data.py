import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from openai import OpenAI
from pymongo import MongoClient
import time
import json

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

def process_with_assistant(client, text_data):
    """Process text data using OpenAI Assistant"""
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
    
    # Merge responses if multiple chunks were processed
    if len(final_responses) > 1:
        logger.info("Merging multiple chunk responses")
        return merge_responses(final_responses)
    
    return json.loads(final_responses[0])

def main():
    """Main function to process data from MongoDB"""
    try:
        # Setup environment
        setup_environment()
        
        # Initialize MongoDB client
        mongo_client = MongoClient(os.getenv('MONGO_DB_URL'))
        source_db = mongo_client[os.getenv('MONGODB_DB_NAME2')]
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Get all documents from source collection
        source_collection = source_db['scraped_data']
        documents = source_collection.find({})
        
        # Process each document
        for doc in documents:
            logger.info(f"Processing document for URL: {doc.get('url', 'Unknown URL')}")
            
            text_content = doc.get('text', '')
            logger.info(f"Document text length: {len(text_content)} characters")
            
            if not text_content:
                logger.warning(f"No text content found for document {doc['_id']}")
                continue
            
            try:
                # Process with OpenAI Assistant
                processed_result = process_with_assistant(openai_client, text_content)
                
                try:
                    # Parse the JSON response
                    processed_data = json.loads(processed_result)
                    
                    # Create separate fields for each component with processed_ prefix
                    update_fields = {
                        "processed_title": processed_data.get("title"),
                        "processed_subtitle": processed_data.get("subtitle"),
                        "processed_author": processed_data.get("author"),
                        "processed_published_date": processed_data.get("published_date"),
                        "processed_key_points": processed_data.get("key_points", []),
                        "processed_key_statistics": processed_data.get("key_statistics", []),
                        "processed_notable_quotes": processed_data.get("notable_quotes", []),
                        "processed_source": processed_data.get("source"),
                        "processed_category_tags": processed_data.get("category_tags", []),
                        "processed_body_text": processed_data.get("body_text"),
                        "processed_additional_fields": processed_data.get("additional_fields", {}),
                        "processed_at": time.time()
                    }
                    
                    # Remove None values
                    update_fields = {k: v for k, v in update_fields.items() if v is not None}
                    
                    # Update MongoDB document
                    update_result = source_collection.update_one(
                        {'_id': doc['_id']},
                        {'$set': update_fields}
                    )
                    
                    logger.info(f"MongoDB update result - Modified count: {update_result.modified_count}")
                    
                    # Verify the update
                    updated_doc = source_collection.find_one({'_id': doc['_id']})
                    if any(field in updated_doc for field in update_fields):
                        logger.info("Document successfully updated with processed fields")
                        logger.info("Updated fields:")
                        for field, value in update_fields.items():
                            if isinstance(value, list):
                                logger.info(f"{field}: {len(value)} items")
                            else:
                                logger.info(f"{field}: {value}")
                    else:
                        logger.warning("Document update verification failed - processed fields not found")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response for document {doc['_id']}: {e}")
                    continue
                
                logger.info(f"Successfully processed and updated data for {doc.get('url', 'Unknown URL')}")
                
            except Exception as e:
                logger.error(f"Error processing document {doc['_id']}: {e}")
                continue
        
        logger.info("Processing completed successfully")
        
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