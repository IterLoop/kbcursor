import os
from pathlib import Path
from scripts.serp import fetch_search_results
from scripts.crawl import MultiCrawler
from scripts.process_data import process_with_assistant
from dotenv import load_dotenv
import json
import logging
from openai import OpenAI
import time
from typing import List, Dict
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('search_runs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

def load_runlist() -> List[Dict]:
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
        
        # Add run start timestamp
        run_start_time = datetime.now()
        logger.info(f"Starting new run at {run_start_time}")
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Load runlist instead of getting user input
        runlist = load_runlist()
        total_searches = len(runlist)
        
        for search_idx, search_item in enumerate(runlist, 1):
            search_term = search_item['search_term']
            results_count = search_item.get('results_count', 10)  # Default to 10 if not specified
            
            # Add search start timestamp
            search_start_time = datetime.now()
            logger.info(f"=== Search Run {search_idx}/{total_searches} Started at {search_start_time} ===")
            
            logger.info(f"\n=== Processing Search {search_idx}/{total_searches} ===")
            logger.info(f"Search term: '{search_term}'")
            logger.info(f"Results count: {results_count}")
            
            # Step 1: Fetch search results (handles its own database operations)
            logger.info(f"Fetching search results for: '{search_term}'")
            search_results = fetch_search_results(search_term, results_count)
            
            # Save results to file for crawler
            results_file = Path(__file__).parent / 'serp_results.json'
            with open(results_file, 'w') as f:
                json.dump(search_results, f)
            
            logger.info(f"Found {len(search_results)} URLs to crawl")
            
            # Step 2: Initialize crawler
            crawler = MultiCrawler(
                apify_api_key=os.getenv('APIFY_API_KEY'),
                mongodb_url=os.getenv('MONGO_DB_URL'),
                serp_db_name=os.getenv('MONGODB_DB_NAME1'),
                crawl_db_name=os.getenv('MONGODB_DB_NAME2')
            )
            
            # Step 3: Crawl each URL
            successful_crawls = 0
            failed_crawls = 0
            processed_docs = 0
            
            for idx, result in enumerate(search_results, 1):
                url = result['url']
                logger.info(f"\nProcessing {idx}/{len(search_results)}: {url}")
                
                try:
                    # Create a CrawlResult with search term
                    crawl_result = crawler.crawl_url(url)
                    if crawl_result:
                        # Add search term to the result
                        crawl_result.search_term = search_term
                        successful_crawls += 1
                        logger.info(f"✓ Successfully crawled: {url}")
                        logger.info(f"  Method: {crawl_result.method}")
                        logger.info(f"  Title: {crawl_result.title}")
                        logger.info(f"  Content length: {len(crawl_result.text)} characters")
                        
                        # Step 4: Process the crawled data (handles its own database operations)
                        try:
                            logger.info(f"\nProcessing content with OpenAI Assistant...")
                            logger.info(f"Content length to process: {len(crawl_result.text)} characters")
                            start_time = time.time()
                            process_with_assistant(openai_client, crawl_result.text, url)
                            processing_time = time.time() - start_time
                            processed_docs += 1
                            logger.info(f"✓ Successfully processed content for: {url}")
                            logger.info(f"  Processing time: {processing_time:.2f} seconds")
                        except Exception as e:
                            logger.error(f"✗ Error processing content for {url}: {str(e)}")
                            logger.error(f"  Error type: {type(e).__name__}")
                    else:
                        failed_crawls += 1
                        logger.error(f"✗ Failed to crawl: {url}")
                except Exception as e:
                    failed_crawls += 1
                    logger.error(f"✗ Error crawling {url}: {e}")
            
            # Enhanced summary with timestamps
            logger.info("\n=== Search Run Summary ===")
            logger.info(f"Search term: '{search_term}'")
            logger.info(f"Start time: {search_start_time}")
            logger.info(f"End time: {datetime.now()}")
            logger.info(f"Total URLs processed: {len(search_results)}")
            logger.info(f"Successful crawls: {successful_crawls}")
            logger.info(f"Failed crawls: {failed_crawls}")
            logger.info(f"Successfully processed documents: {processed_docs}")
            logger.info("=====================")
        
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
