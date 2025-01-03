from apify_client import ApifyClient
import json
import os
from typing import List, Dict
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv

class SerpAgent:
    def __init__(self, api_key: str, mongo_uri: str):
        self.client = ApifyClient(api_key)
        self.actor_id = "apify/google-search-scraper"
        # Initialize MongoDB client
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.search_results
        
    def search(self, queries: List[str], country_code: str = "us", language: str = "en") -> List[Dict]:
        """
        Perform Google searches using Apify's Google Search Scraper
        
        Args:
            queries: List of search queries
            country_code: Country code for search results (default: us)
            language: Language code for search results (default: en)
            
        Returns:
            List of search results
        """
        # Prepare the input for the actor
        run_input = {
            "queries": "\n".join(queries),
            "countryCode": country_code,
            "languageCode": language,
            "maxPagesPerQuery": 1,
            "resultsPerPage": 1,
            "mobileResults": False,
            "saveHtml": False
        }

        # Run the actor and wait for it to finish
        run = self.client.actor(self.actor_id).call(run_input=run_input)

        # Fetch results from the actor's default dataset
        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(item)
            
        return results

    def save_results(self, results: List[Dict], output_file: str = "search_results.json"):
        """
        Save search results to a JSON file
        
        Args:
            results: List of search results
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def clean_results(self, results: List[Dict], target_domains: List[str] = None) -> List[str]:
        """
        Clean search results to extract URLs from specified domains
        
        Args:
            results: List of raw search results
            target_domains: List of domain names to filter (e.g., ['ibm.com', 'microsoft.com'])
            
        Returns:
            List of cleaned URLs matching the target domains
        """
        target_url = "https://www.ibm.com/think/topics/ai-supply-chain"
        cleaned_urls = []
        for result in results:
            organic_results = result.get('organicResults', [])
            for item in organic_results:
                url = item.get('url')
                if url and (not target_domains or any(domain in url for domain in target_domains)):
                    cleaned_urls.append({
                        'url': url,
                        'title': item.get('title'),
                        'description': item.get('description'),
                        'timestamp': datetime.datetime.utcnow()
                    })
        return cleaned_urls

    def save_cleaned_results(self, urls: List[str], output_file: str = "cleaned_urls.txt"):
        """
        Save cleaned URLs to a text file
        
        Args:
            urls: List of cleaned URLs
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")

    def save_to_mongodb(self, results: List[Dict], collection_name: str = 'search_results'):
        """
        Save results to MongoDB
        
        Args:
            results: List of search results
            collection_name: Name of the MongoDB collection
        """
        collection = self.db[collection_name]
        collection.insert_many(results)

def main(search_term: str = None, target_domains: List[str] = None):
    # Load environment variables from .env file
    load_dotenv()
    
    # Get environment variables
    api_key = os.getenv('APIFY_API_KEY')
    mongo_uri = os.getenv('MONGO_DB_URI')
    
    if not api_key:
        raise ValueError("APIFY_API_KEY environment variable is not set")
    if not mongo_uri:
        raise ValueError("MONGO_DB_URI environment variable is not set")
    
    # Get search term from parameter, command line argument, or prompt user
    if search_term is None:
        if len(sys.argv) > 1:
            search_term = sys.argv[1]
        else:
            search_term = input("Please enter a search term: ")
    # Get API key from environment variable
    api_key = os.getenv('APIFY_API_KEY')
    if not api_key:
        raise ValueError("APIFY_API_KEY environment variable is not set")
    
    agent = SerpAgent(api_key)

    try:
        print("Starting search...")
        results = agent.search(queries)
        
        # Clean results with optional domain filtering
        cleaned_urls = agent.clean_results(results, target_domains)
        
        # Save to both file and MongoDB
        agent.save_cleaned_results(cleaned_urls)
        agent.save_to_mongodb(cleaned_urls)
        
        print(f"Search completed! Found {len(cleaned_urls)} cleaned URLs.")
        print("Results saved to MongoDB and cleaned_urls.txt")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    # Example usage with specific domains to filter
    target_domains = ['ibm.com', 'microsoft.com']  # Can be modified or passed as argument
    main(target_domains=target_domains)
