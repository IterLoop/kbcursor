import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass
import hashlib
import urllib.parse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from apify_client import ApifyClient
from pymongo import MongoClient
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import re
from config import MONGO_DB_URL, SEARCH_DB, CONTENT_DB, RAW_CONTENT_COLLECTION
from tools.mongo import MongoValidator, RAW_CONTENT_SCHEMA

def is_content_relevant_to_title(title: str, content: str, threshold: float = 0.2) -> bool:
    """
    Checks whether the content is relevant to the given title by computing
    a simple TF-IDF-based cosine similarity. If the similarity is below
    `threshold`, it is considered 'off-topic'.

    :param title: The article's title.
    :param content: The full text content of the article.
    :param threshold: Cosine similarity threshold. Higher means stricter.
    :return: True if relevant, False if off-topic.
    """
    # Basic sanity checks
    if not title or not content:
        return True  # If we don't have enough info, assume it's okay or handle differently

    # Optional: Basic text cleanup (remove special characters, extra spaces, etc.)
    def basic_clean(text):
        text = re.sub(r'[\r\n]+', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower().strip()

    title_clean = basic_clean(title)
    content_clean = basic_clean(content)

    # TF-IDF vectorization
    corpus = [title_clean, content_clean]
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform(corpus).toarray()

    if len(vectorizer.get_feature_names_out()) == 0:
        # If there's no overlap in vocabulary at all, consider it off-topic 
        # or handle it differently
        return False

    # vectors[0] -> TF-IDF for title, vectors[1] -> TF-IDF for content
    # Cosine similarity
    title_vec = vectors[0]
    content_vec = vectors[1]

    similarity = np.dot(title_vec, content_vec) / (
        np.linalg.norm(title_vec) * np.linalg.norm(content_vec)
        + 1e-9  # Avoid division by zero
    )

    # Return True if above threshold, else False
    return similarity >= threshold

# Define root directory
ROOT_DIR = Path(__file__).parent.parent

# Load environment variables from the secrets folder
env_path = ROOT_DIR / 'secrets' / '.env'
print(f"Loading .env from: {env_path}")

# Debug: Print environment file contents
try:
    with open(env_path, 'r') as f:
        env_contents = f.read()
        print("\nEnvironment file contents:")
        for line in env_contents.splitlines():
            if line.strip() and not line.startswith('#'):
                key = line.split('=')[0].strip()
                print(f"Found key: {key}")
except Exception as e:
    print(f"Error reading .env file: {e}")

# Load environment variables
load_dotenv(env_path)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    url: str
    title: Optional[str]
    text: str
    metadata: Dict[str, Any]
    crawl_time: datetime
    method: str

class MultiCrawler:
    def __init__(self, apify_api_key: str):
        try:
            self.apify_client = ApifyClient(apify_api_key)
            self.mongo_client = MongoClient(MONGO_DB_URL)
            
            # Initialize both databases
            self.serp_db = self.mongo_client[SEARCH_DB]
            self.crawl_db = self.mongo_client[CONTENT_DB]
            
            # Collections - updated to new structure
            self.collection = self.crawl_db[RAW_CONTENT_COLLECTION]
            
            # Verify connections first
            self._verify_connections()
            
            # Setup indexes after verifying connection
            self._setup_indexes()
            
        except Exception as e:
            logger.error(f"Failed to initialize crawler: {e}")
            raise

    def _verify_connections(self):
        """Verify both Apify and MongoDB connections"""
        try:
            # Test Apify connection
            self.apify_client.user().get()
            logger.info("Successfully connected to Apify")
            
            # Test MongoDB connection
            self.mongo_client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Log database and collection names
            logger.info(f"Using SERP database: {self.serp_db.name}")
            logger.info(f"Using Content database: {self.crawl_db.name}")
            logger.info(f"Using collection: {RAW_CONTENT_COLLECTION}")
            
            # Verify collections exist
            collections = self.crawl_db.list_collection_names()
            logger.info(f"Available collections: {collections}")
            
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            raise

    def _setup_indexes(self):
        """Setup necessary database indexes"""
        try:
            # Indexes for raw_content collection
            self.collection.create_index(
                [("url", 1)], 
                unique=True,
                name="url_1"
            )
            self.collection.create_index(
                [("crawl_time", 1)], 
                name="crawl_time_1"
            )
            self.collection.create_index(
                [("content_hash", 1)], 
                name="content_hash_1"
            )
            
            logger.info("MongoDB indexes verified")
            
            # Verify indexes match expected structure
            content_indexes = list(self.collection.list_indexes())
            logger.debug(f"Raw content indexes: {[idx['name'] for idx in content_indexes]}")
            
        except Exception as e:
            logger.error(f"Index verification failed: {e}")
            # Continue execution as indexes already exist
            pass

    def _get_url_hash(self, content: str) -> str:
        """Generate hash of content to detect changes"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _check_last_modified(self, url: str) -> Optional[datetime]:
        """Check if the URL content has been modified"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Try HEAD request first
            response = requests.head(url, headers=headers, timeout=5)
            
            # Check Last-Modified header
            last_modified = response.headers.get('Last-Modified')
            if last_modified:
                return datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
            
            # Check ETag
            etag = response.headers.get('ETag')
            if etag:
                return datetime.now(UTC)  # If ETag changed, force recrawl
                
            return None
            
        except Exception as e:
            logger.warning(f"Failed to check last modified for {url}: {e}")
            return None

    def should_crawl(self, url: str) -> tuple[bool, Optional[dict]]:
        """
        Determine if URL should be crawled based on tracking data
        Returns: (should_crawl: bool, existing_data: Optional[dict])
        """
        try:
            # Check raw_content collection for existing data
            existing_doc = self.collection.find_one({"url": url})
            
            if not existing_doc:
                logger.info(f"URL {url} has never been crawled")
                return True, None
            
            last_crawl_date = existing_doc['crawl_time']
            
            # Check if minimum crawl interval has passed (default: 7 days)
            min_interval = timedelta(days=7)
            if datetime.now(UTC) - last_crawl_date < min_interval:
                logger.info(f"URL {url} was recently crawled")
                return False, existing_doc
            
            # Check if content has been modified
            last_modified = self._check_last_modified(url)
            
            if last_modified and last_modified <= last_crawl_date:
                logger.info(f"Content for {url} hasn't changed since last crawl")
                return False, existing_doc
            
            logger.info(f"Content for {url} needs to be recrawled")
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking crawl status for {url}: {e}")
            return True, None  # Crawl on error to be safe

    def _store_result(self, result: CrawlResult):
        """Store crawl result in MongoDB with proper error handling"""
        try:
            # Get existing document if any
            existing_doc = self.collection.find_one({"url": result.url})
            current_time = datetime.now(UTC)
            
            # Prepare metadata
            crawl_meta = {
                "method": result.method,
                "crawl_time": current_time,
                "updated_at": current_time,
                "content_hash": self._get_url_hash(result.text),
                "word_count": len(result.text.split()),
                "status": "success",
                "attempts": (existing_doc.get("metadata", {}).get("crawl_meta", {}).get("attempts", 0) + 1) if existing_doc else 1,
                "last_success": current_time,
                "last_failure": existing_doc.get("metadata", {}).get("crawl_meta", {}).get("last_failure"),
                "failure_reason": None
            }
            
            # Prepare document for MongoDB
            document = {
                "url": result.url,
                "title": result.title,
                "text": result.text,
                "metadata": {
                    "source_meta": result.metadata,  # Original metadata from source
                    "crawl_meta": crawl_meta
                },
                "method": result.method,
                "crawl_time": current_time,
                "updated_at": current_time,
                "word_count": len(result.text.split()),
                "status": "success",
                "content_hash": self._get_url_hash(result.text)
            }
            
            # Validate document against schema
            document = MongoValidator.prepare_for_mongodb(document, RAW_CONTENT_SCHEMA)
            
            # Upsert the document
            self.collection.update_one(
                {"url": result.url},
                {"$set": document},
                upsert=True
            )
            
            logger.info(f"Successfully stored/updated content for {result.url}")
            
        except Exception as e:
            logger.error(f"Error storing result for {result.url}: {e}")
            raise

    def _record_crawl_failure(self, url: str, reason: str = "Unknown error"):
        """Record failed crawl attempt with metadata"""
        try:
            # Get existing document if any
            existing_doc = self.collection.find_one({"url": url})
            current_time = datetime.now(UTC)
            
            # Prepare metadata
            crawl_meta = {
                "method": "failed",
                "crawl_time": current_time,
                "updated_at": current_time,
                "content_hash": None,
                "word_count": 0,
                "status": "failed",
                "attempts": (existing_doc.get("metadata", {}).get("crawl_meta", {}).get("attempts", 0) + 1) if existing_doc else 1,
                "last_success": existing_doc.get("metadata", {}).get("crawl_meta", {}).get("last_success"),
                "last_failure": current_time,
                "failure_reason": reason
            }
            
            tracking_data = {
                "url": url,
                "title": None,
                "text": "",
                "metadata": {
                    "source_meta": {},
                    "crawl_meta": crawl_meta
                },
                "method": "failed",
                "crawl_time": current_time,
                "updated_at": current_time,
                "word_count": 0,
                "status": "failed",
                "content_hash": None
            }
            
            # Validate document against schema
            tracking_data = MongoValidator.prepare_for_mongodb(tracking_data, RAW_CONTENT_SCHEMA)
            
            self.collection.update_one(
                {"url": url},
                {"$set": tracking_data},
                upsert=True
            )
            
            logger.info(f"Recorded crawl failure for {url}: {reason}")
            
        except Exception as e:
            logger.error(f"Error recording crawl failure for {url}: {e}")
            raise

    def crawl_url(self, url: str) -> Optional[CrawlResult]:
        """Try different crawling methods with fallback strategy"""
        # Validate URL
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid URL")
        except Exception:
            logger.error(f"Invalid URL provided: {url}")
            return None

        # Check if URL should be crawled
        should_crawl, existing_data = self.should_crawl(url)
        
        if not should_crawl and existing_data:
            logger.info(f"Using existing data for {url}")
            return CrawlResult(
                url=existing_data['url'],
                title=existing_data['title'],
                text=existing_data['text'],
                metadata=existing_data['metadata'],
                crawl_time=existing_data['crawl_time'],
                method=existing_data['method']
            )

        # Skip if it's a Google search URL
        if 'google.com/search' in url:
            logger.warning(f"Skipping Google search URL: {url}")
            return None

        # Separate free crawlers and Apify
        free_crawlers = [
            ("BeautifulSoup Static", self._static_crawl),
            ("Playwright Dynamic", self._js_crawl),
            ("Selenium Fallback", self._selenium_crawl),
            ("Scrapy Fallback", self._scrapy_crawl)
        ]

        # Try each free crawler first
        for crawler_name, crawler_method in free_crawlers:
            logger.info(f"Attempting {crawler_name} crawler for: {url}")
            try:
                result = crawler_method(url)
                if result and result.text and len(result.text) > 100:
                    logger.info(f"Successfully crawled with {crawler_name}")
                    
                    # Check if title and text are coherent using NLP
                    if result.title and result.text:
                        if is_content_relevant_to_title(result.title, result.text):
                            # Content is relevant, store and return
                            try:
                                self._store_result(result)
                                logger.info(f"Successfully stored crawl result in MongoDB")
                                return result
                            except Exception as e:
                                logger.error(f"Failed to store crawl result in MongoDB: {e}")
                                continue
                        else:
                            logger.warning(
                                f"Content for '{url}' from {crawler_name} is off-topic relative to '{result.title}'. "
                                "Trying next crawler."
                            )
                            continue
                    else:
                        logger.warning(f"{crawler_name} crawler failed to get title or text")
                else:
                    logger.warning(f"{crawler_name} crawler failed to get sufficient content")
            except Exception as e:
                logger.error(f"{crawler_name} crawler failed with error: {e}")
                continue

        # If all free crawlers failed or got irrelevant content, try Apify
        logger.info("All free crawlers failed or got irrelevant content. Attempting Apify crawler.")
        try:
            apify_result = self._apify_crawl(url)
            if apify_result and apify_result.text:
                if not apify_result.title or is_content_relevant_to_title(apify_result.title, apify_result.text):
                    logger.info("Apify crawler retrieved content")
                    try:
                        self._store_result(apify_result)
                        logger.info("Successfully stored Apify result in MongoDB")
                        return apify_result
                    except Exception as e:
                        logger.error(f"Failed to store Apify result in MongoDB: {e}")
                else:
                    logger.warning("Apify crawler content appears off-topic")
            else:
                logger.warning("Apify crawler failed to get sufficient content")
        except Exception as e:
            logger.error(f"Apify crawler failed with error: {e}")

        logger.error(f"All crawling methods failed for: {url}")
        self._record_crawl_failure(url)
        return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _static_crawl(self, url: str) -> Optional[CrawlResult]:
        """Simple static page crawler using requests"""
        try:
            logger.info(f"Attempting static crawl for: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            
            if not text:
                return None
                
            return CrawlResult(
                url=url,
                title=soup.title.string if soup.title else None,
                text=text,
                metadata=self._extract_metadata(soup),
                crawl_time=datetime.now(UTC),
                method="static"
            )
        except Exception as e:
            logger.error(f"Static crawler failed for {url}: {e}")
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _js_crawl(self, url: str) -> Optional[CrawlResult]:
        """JavaScript-enabled crawler using Playwright"""
        logger.info(f"Attempting JavaScript crawl for: {url}")
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()
                page.set_default_timeout(30000)
                
                # Wait for network idle to ensure JS content loads
                page.goto(url, wait_until="networkidle")
                
                # Wait for common content selectors
                selectors = ["article", "main", ".content", "#content"]
                for selector in selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                    except:
                        continue
                
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                
                if not text:
                    return None
                    
                result = CrawlResult(
                    url=url,
                    title=soup.title.string if soup.title else None,
                    text=text,
                    metadata={
                        **self._extract_metadata(soup),
                        'final_url': page.url
                    },
                    crawl_time=datetime.now(UTC),
                    method="javascript"
                )
                
                return result
                
        except Exception as e:
            logger.error(f"JavaScript crawler failed for {url}: {e}")
            return None
        finally:
            if browser:
                browser.close()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=4, max=30))
    def _apify_crawl(self, url: str) -> Optional[CrawlResult]:
        """Apify website-content-crawler as last resort"""
        try:
            logger.info(f"Attempting Apify crawl for: {url}")
            
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlingDepth": 1,
                "maxPagesPerCrawl": 1,
                "additionalMimeTypes": ["text/markdown", "text/plain"],
                "proxyConfiguration": {"useApifyProxy": True}
            }
            
            run = self.apify_client.actor("apify/website-content-crawler").call(run_input=run_input)
            items = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items
            
            if not items:
                return None
                
            item = items[0]
            if not item.get('text'):
                return None
                
            return CrawlResult(
                url=url,
                title=item.get('title'),
                text=item.get('text', ''),
                metadata={
                    'loadedUrl': item.get('loadedUrl'),
                    'loadedTime': item.get('loadedTime'),
                    'pageType': item.get('pageType'),
                    **item.get('metadata', {})
                },
                crawl_time=datetime.now(UTC),
                method="apify"
            )
            
        except Exception as e:
            logger.error(f"Apify crawler failed for {url}: {e}")
            return None

    @staticmethod
    def _extract_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object"""
        metadata = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property'))
            content = meta.get('content')
            if name and content:
                metadata[name] = content
        return metadata

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _selenium_crawl(self, url: str) -> Optional[CrawlResult]:
        """Selenium-based crawler as another fallback"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            logger.info(f"Attempting Selenium crawl for: {url}")
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            with webdriver.Chrome(options=chrome_options) as driver:
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(("tag name", "body"))
                )
                
                content = driver.page_source
                soup = BeautifulSoup(content, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                
                if not text:
                    return None
                    
                return CrawlResult(
                    url=url,
                    title=driver.title,
                    text=text,
                    metadata={
                        **self._extract_metadata(soup),
                        'final_url': driver.current_url
                    },
                    crawl_time=datetime.now(UTC),
                    method="selenium"
                )
                
        except Exception as e:
            logger.error(f"Selenium crawler failed for {url}: {e}")
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _scrapy_crawl(self, url: str) -> Optional[CrawlResult]:
        """Scrapy-based crawler as another fallback"""
        try:
            import scrapy
            from scrapy.crawler import CrawlerProcess
            from scrapy.http import TextResponse
            
            logger.info(f"Attempting Scrapy crawl for: {url}")
            
            class SinglePageSpider(scrapy.Spider):
                name = 'single_page'
                start_urls = [url]
                
                def parse(self, response: TextResponse):
                    return {
                        'url': response.url,
                        'title': response.css('title::text').get(),
                        'text': ' '.join(response.css('body ::text').getall()),
                        'metadata': {
                            meta.attrib.get('name', meta.attrib.get('property')): meta.attrib['content']
                            for meta in response.css('meta[content]')
                            if meta.attrib.get('name') or meta.attrib.get('property')
                        }
                    }
            
            results = []
            process = CrawlerProcess(settings={
                'LOG_ENABLED': False,
                'ROBOTSTXT_OBEY': True,
                'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            def collect_result(item):
                results.append(item)
            
            process.crawl(SinglePageSpider)
            process.start()
            
            if results:
                result = results[0]
                return CrawlResult(
                    url=result['url'],
                    title=result['title'],
                    text=result['text'],
                    metadata=result['metadata'],
                    crawl_time=datetime.now(UTC),
                    method="scrapy"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Scrapy crawler failed for {url}: {e}")
            return None

    def verify_storage(self, url: str):
        """Verify data storage for a URL"""
        try:
            # Check raw_content collection
            doc = self.collection.find_one({"url": url})
            if doc:
                logger.info(f"Found document in raw_content:")
                logger.info(f"Title: {doc.get('title')}")
                logger.info(f"Method: {doc.get('method')}")
                logger.info(f"Word count: {doc.get('word_count')}")
            else:
                logger.error(f"No document found for URL: {url}")
            
            # Check url_tracking collection
            tracking = self.collection.find_one({"url": url})
            if tracking:
                logger.info(f"Found tracking data:")
                logger.info(f"Last crawl: {tracking.get('last_crawl_date')}")
                logger.info(f"Success: {tracking.get('success')}")
            else:
                logger.error(f"No tracking data found for URL: {url}")
                
        except Exception as e:
            logger.error(f"Error verifying storage: {e}")

def main():
    # Get environment variables with debug output
    env_vars = {
        'APIFY_API_KEY': os.getenv('APIFY_API_KEY'),
        'MONGO_DB_URL': os.getenv('MONGO_DB_URL'),
        'MONGODB_DB_NAME1': os.getenv('MONGODB_DB_NAME1'),
        'MONGODB_DB_NAME2': os.getenv('MONGODB_DB_NAME2')
    }
    
    # Debug logging for environment variables
    print("\nEnvironment Variables:")
    for key, value in env_vars.items():
        masked_value = '***' if value and key == 'APIFY_API_KEY' else value
        print(f"{key}: {masked_value}")
    
    if not all(env_vars.values()):
        missing_vars = [key for key, value in env_vars.items() if not value]
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        raise ValueError("Missing required environment variables")
    
    # Initialize crawler
    crawler = MultiCrawler(
        apify_api_key=env_vars['APIFY_API_KEY']
    )
    
    # Get URLs from SERP results or user input
    serp_path = ROOT_DIR / 'serp_results.json'
    try:
        with open(serp_path, 'r') as f:
            import json
            serp_data = json.load(f)
            if isinstance(serp_data, list):
                urls = [item.get('url') for item in serp_data if item.get('url')]
            else:
                logger.error("Invalid SERP results format")
                urls = []
    except FileNotFoundError:
        logger.info(f"No SERP results found at {serp_path}, requesting manual URL input")
        urls = [input("Enter the URL to crawl: ").strip()]
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {serp_path}")
        urls = [input("Enter the URL to crawl: ").strip()]
    
    if not urls:
        logger.error("No valid URLs to process")
        return
    
    # Process URLs
    total_urls = len(urls)
    successful_crawls = 0
    
    for index, url in enumerate(urls, 1):
        logger.info(f"Processing URL {index}/{total_urls}: {url}")
        
        if not url:
            logger.warning("Skipping empty URL")
            continue
            
        try:
            result = crawler.crawl_url(url)
            if result:
                successful_crawls += 1
                logger.info(f"Successfully processed {url}")
                logger.info(f"Method: {result.method}")
                logger.info(f"Title: {result.title}")
                logger.info(f"Content length: {len(result.text)} characters")
                crawler.verify_storage(url)
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            continue
    
    # Log summary
    logger.info("\nCrawl Summary:")
    logger.info(f"Total URLs processed: {total_urls}")
    logger.info(f"Successful crawls: {successful_crawls}")
    logger.info(f"Failed crawls: {total_urls - successful_crawls}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCrawling interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Crawling process completed")
