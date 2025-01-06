import json
import sys
import logging
import time
from pathlib import Path
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_runlist(file_path):
    """Load and validate the runlist JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or 'search_terms' not in data:
            raise ValueError("Invalid JSON structure. Expected {'search_terms': [...]}")
        
        return data['search_terms']
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading runlist file: {e}")
        raise

def run_search(search_term, results_count):
    """Run main.py with the given search term and results count"""
    try:
        # Create a process to run main.py
        process = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send the search term and results count
        inputs = f"{search_term}\n{results_count}\n"
        stdout, stderr = process.communicate(inputs)
        
        if process.returncode != 0:
            logger.error(f"Error running search for '{search_term}': {stderr}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error running search for '{search_term}': {e}")
        return False

def main():
    try:
        # Load the runlist
        runlist_path = Path('runlist.json')
        logger.info(f"Loading runlist from {runlist_path}")
        search_terms = load_runlist(runlist_path)
        
        total_terms = len(search_terms)
        successful = 0
        failed = 0
        
        logger.info(f"Found {total_terms} search terms to process")
        
        # Process each search term
        for idx, item in enumerate(search_terms, 1):
            term = item['term']
            results = item['results_to_scrape']
            
            logger.info(f"\nProcessing {idx}/{total_terms}")
            logger.info(f"Search Term: {term}")
            logger.info(f"Results to scrape: {results}")
            
            if run_search(term, results):
                successful += 1
                logger.info("✓ Successfully completed search")
            else:
                failed += 1
                logger.info("✗ Failed to complete search")
            
            # Add a small delay between searches
            if idx < total_terms:
                time.sleep(5)  # 5 second delay between searches
        
        # Print summary
        logger.info("\n=== Batch Processing Summary ===")
        logger.info(f"Total search terms: {total_terms}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info("============================")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
    finally:
        logger.info("Batch processing completed") 