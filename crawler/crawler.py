import logging
from typing import Optional, Dict, Any, Set
from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential
from dataclasses import dataclass
from apify_client._errors import ApifyApiError
import time  # Add this at the top with other imports
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class WebContent:
    url: str
    title: Optional[str]
    text: str
    metadata: Dict[str, Any]
    source: str

class WebCrawler:
    def __init__(self, apify_api_key: Optional[str] = None):
        self.apify_api_key = apify_api_key
        if self.apify_api_key:
            self.apify_client = ApifyClient(self.apify_api_key)
            logger.info("Successfully initialized Apify client")
            try:
                # Test API key validity
                self.apify_client.user().get()
                logger.info("Apify API key verified successfully")
            except Exception as e:
                logger.error(f"Failed to verify Apify API key: {str(e)}")
                raise ValueError("Invalid Apify API key")
        else:
            logger.error("No Apify API key provided")
            raise ValueError("Apify API key is required")
    
    @staticmethod
    def extract_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object"""
        metadata = {}
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property'))
            content = meta.get('content')
            if name and content:
                metadata[name] = content
                
        return metadata

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def static_crawl(self, url: str) -> Optional[WebContent]:
        """Simple static page crawler using requests"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            return WebContent(
                url=url,
                title=soup.title.string if soup.title else None,
                text=soup.get_text(separator=" ", strip=True),
                metadata=self.extract_metadata(soup),
                source="static"
            )
        except Exception as e:
            logger.error(f"Static crawler failed for {url}: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def js_crawl(self, url: str) -> Optional[WebContent]:
        """JavaScript-enabled crawler using Playwright"""
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(30000)
                page.goto(url)
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                return WebContent(
                    url=url,
                    title=soup.title.string if soup.title else None,
                    text=soup.get_text(separator=" ", strip=True),
                    metadata=self.extract_metadata(soup),
                    source="javascript"
                )
        except Exception as e:
            logger.error(f"JS crawler failed for {url}: {e}")
            return None
        finally:
            if browser:
                try:
                    browser.close()
                except Exception as e:
                    logger.warning(f"Failed to close browser for {url}: {e}")

    def apify_crawl(self, url: str) -> Optional[WebContent]:
        """Apify-based crawler as a fallback option"""
        if not self.apify_api_key:
            logger.error("Apify API key not provided")
            return None
            
        try:
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlingDepth": 1,
                "maxPagesPerCrawl": 1,
                "additionalMimeTypes": ["text/markdown", "text/plain"],
            }
            
            run = self.apify_client.actor("apify/website-content-crawler").call(run_input=run_input)
            
            # Get the first result
            for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                return WebContent(
                    url=url,
                    title=item.get('title'),
                    text=item.get('text', ''),
                    metadata={
                        'loadedUrl': item.get('loadedUrl'),
                        'loadedTime': item.get('loadedTime'),
                        'referrerUrl': item.get('referrerUrl'),
                        'depth': item.get('depth'),
                        **item.get('metadata', {})
                    },
                    source="apify"
                )
            
            return None
        except Exception as e:
            logger.error(f"Apify crawler failed for {url}: {e}")
            return None

    def crawl_with_fallback(self, url: str) -> Optional[WebContent]:
        """Try different crawling methods with fallback"""
        logger.info(f"Starting crawl for URL: {url}")
        
        # Skip if it's a Google search URL
        if 'google.com/search' in url:
            logger.warning(f"Skipping Google search URL: {url}")
            return None

        # 1. Try static crawler first
        logger.info(f"Attempting static crawl for: {url}")
        content = self.static_crawl(url)
        if content and content.text.strip():
            logger.info("Static crawl successful")
            return content

        # 2. Try JavaScript crawler
        logger.info("Static crawl failed, attempting JS crawl")
        content = self.js_crawl(url)
        if content and content.text.strip():
            logger.info("JS crawl successful")
            return content

        # 3. Try Apify website content crawler as last resort
        if self.apify_api_key:
            logger.info("JS crawl failed, attempting Apify website content crawler")
            content = self.apify_crawl(url)
            if content and content.text.strip():
                logger.info("Apify crawl successful")
                return content

        logger.error(f"All crawling methods failed for: {url}")
        return None 

    def get_search_results(self, search_term: str, max_urls: int) -> Set[str]:
        """Get URLs from Google Search using Apify's Google Search Scraper"""
        logger.info(f"Getting search results for: {search_term}")
        
        MAX_RETRIES = 3
        TIMEOUT_SECONDS = 10  # Wait 10 seconds between retries
        
        run_input = {
            "queries": search_term,
            "maxPagesPerQuery": max_urls,
            "resultsPerPage": max_urls,
            "memoryMbytes": 512,
            "includeUnfilteredResults": False,  # Only get organic results
            "mobileResults": False,  # Desktop results tend to be more reliable
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                # Run the actor
                run = self.apify_client.actor("apify/google-search-scraper").call(run_input=run_input)
                
                # Get dataset items
                dataset_items = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items
                
                # Extract only organic result URLs
                urls = set()
                for item in dataset_items:
                    if isinstance(item, dict):
                        # Get organic results only
                        organic_results = item.get('organicResults', [])
                        for result in organic_results:
                            if isinstance(result, dict) and 'url' in result:
                                urls.add(result['url'])
                
                logger.info(f"Found {len(urls)} organic URLs from search results")
                logger.debug(f"Retrieved URLs: {urls}")
                
                if urls:  # Only return if we found some URLs
                    return urls
                
                # If no URLs found but no error, try again after delay
                logger.warning(f"No URLs found on attempt {attempt + 1}, retrying...")
                time.sleep(TIMEOUT_SECONDS)
                
            except apify_client._errors.ApifyApiError as e:
                if "memory limit" in str(e).lower():
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Hit memory limit, waiting {TIMEOUT_SECONDS} seconds before retry {attempt + 1}/{MAX_RETRIES}")
                        time.sleep(TIMEOUT_SECONDS)
                    else:
                        logger.error("Exceeded maximum retries for memory limit")
                        return set()
                else:
                    logger.error(f"Failed to get search results: {str(e)}", exc_info=True)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(TIMEOUT_SECONDS)
                        continue
                    return set()
            except Exception as e:
                logger.error(f"Failed to get search results: {str(e)}", exc_info=True)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(TIMEOUT_SECONDS)
                    continue
                return set()
        
        return set() 