import os
import json
from apify_client import ApifyClient
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any
from pymongo import MongoClient
from datetime import datetime

# Get the project root directory (parent of scripts folder)
ROOT_DIR = Path(__file__).parent.parent

# Load environment variables from secrets/.env
env_path = os.path.join(ROOT_DIR, 'secrets', '.env')
print(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)

def connect_to_mongodb():
    """Connect to local MongoDB instance."""
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['searchresults']
        print("Successfully connected to MongoDB")
        return db
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        raise

def save_to_mongodb(results: List[Dict[str, Any]], search_term: str):
    """Save results to MongoDB with timestamp and search term."""
    try:
        db = connect_to_mongodb()
        collection = db['searches']
        
        document = {
            'search_term': search_term,
            'timestamp': datetime.utcnow(),
            'results': results
        }
        
        result = collection.insert_one(document)
        print(f"Saved to MongoDB with ID: {result.inserted_id}")
        
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        raise

def fetch_search_results(search_term: str, results_per_page: int) -> List[Dict[str, Any]]:
    """Fetch search results and return list of dicts with url and meta_tags."""
    api_key = os.getenv("APIFY_API_KEY")
    
    if not api_key:
        raise ValueError("APIFY_API_KEY environment variable is not set")
    
    try:
        apify_client = ApifyClient(api_key)
        run_input = {
            "queries": search_term,
            "maxPagesPerQuery": 1,
            "resultsPerPage": results_per_page,
            "maxCrawlPages": 1,
            "mobileResults": False,
            "languageCode": "en",
            "maxConcurrency": 1,
            "memoryMbytes": 512,
        }

        print("Starting Apify search...")
        run = apify_client.actor("apify/google-search-scraper").call(run_input=run_input)
        
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ValueError("No dataset ID returned from Apify")
            
        items = apify_client.dataset(dataset_id).list_items().items
        
        processed_results = []
        for item in items:
            if isinstance(item, dict):
                organic_results = item.get('organicResults', [])
                for result in organic_results:
                    if not isinstance(result, dict):
                        continue
                        
                    url = result.get("url", "")
                    if not url:
                        continue
                        
                    processed_results.append({
                        "url": url,  # Now storing the full URL
                        "meta_tags": {
                            "title": result.get("title"),
                            "description": result.get("description"),
                        }
                    })
        
        print(f"Found {len(processed_results)} results")
        return processed_results

    except Exception as e:
        print(f"Error in search: {str(e)}")
        raise

def main():
    try:
        # Test MongoDB connection at startup
        db = connect_to_mongodb()
        print("MongoDB connection test successful")
        
        search_term = input("Enter the search term: ")
        results_per_page = int(input("Enter the number of results per page: "))

        # Fetch and process results
        results = fetch_search_results(search_term, results_per_page)

        # Save to MongoDB
        save_to_mongodb(results, search_term)

        # Print results
        print("\nResults:")
        print(json.dumps(results, indent=4))
        
        return results

    except Exception as e:
        print(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()