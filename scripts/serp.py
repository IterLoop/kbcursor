import os
import json
from apify_client import ApifyClient
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any

# Get the project root directory (parent of scripts folder)
ROOT_DIR = Path(__file__).parent.parent

# Load environment variables from secrets/.env
env_path = os.path.join(ROOT_DIR, 'secrets', '.env')
print(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)

def extract_base_url(url: str) -> str:
    """Extract the base URL from a given URL."""
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"

def fetch_search_results(search_term: str, results_per_page: int) -> List[Dict[str, Any]]:
    """
    Fetch search results and return list of dicts with base_url and meta_tags.
    Returns: List[Dict[str, Any]] where each dict has:
        - base_url: str
        - meta_tags: Dict containing title and description
    """
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
                        "base_url": extract_base_url(url),
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
    search_term = input("Enter the search term: ")
    results_per_page = int(input("Enter the number of results per page: "))

    # Fetch and process results in one step
    results = fetch_search_results(search_term, results_per_page)

    # Print results
    print("\nResults:")
    print(json.dumps(results, indent=4))
    
    return results  # Return results for potential further use

if __name__ == "__main__":
    main()