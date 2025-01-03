from apify_client import ApifyClient
import json
import os
from typing import List, Dict

class SerpAgent:
    def __init__(self, api_key: str):
        self.client = ApifyClient(api_key)
        # Actor ID for Google Search Scraper
        self.actor_id = "apify/google-search-scraper"

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

    def clean_results(self, results: List[Dict]) -> List[str]:
        """
        Clean search results to extract only specific URLs
        
        Args:
            results: List of raw search results
            
        Returns:
            List of cleaned URLs (only IBM URL in this case)
        """
        target_url = "https://www.ibm.com/think/topics/ai-supply-chain"
        cleaned_urls = []
        for result in results:
            organic_results = result.get('organicResults', [])
            for item in organic_results:
                url = item.get('url')
                if url and url == target_url:
                    cleaned_urls.append(url)
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

def main():
    # Initialize the SERP agent with your API key
    api_key = "apify_api_RqJ95dSauHAkMv1WGiajI2ysI8zAlg04FzoV"
    agent = SerpAgent(api_key)

    # Example search queries
    queries = [
        "Supply chain AI",
    ]

    try:
        # Perform the search
        print("Starting search...")
        results = agent.search(queries)
        
        # Clean and save results
        cleaned_urls = agent.clean_results(results)
        agent.save_cleaned_results(cleaned_urls)
        
        print(f"Search completed! Found {len(cleaned_urls)} cleaned URLs.")
        print("Cleaned URLs saved to cleaned_urls.txt")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
