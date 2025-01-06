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
import io
import PyPDF2
from pdfminer.high_level import extract_text
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
import time
import random

def is_content_relevant_to_title(title: str, text: str) -> bool:
    """Check if content is relevant to the title using NLP"""
    try:
        # Clean and normalize text
        title = title.lower().strip()
        text = text.lower().strip()
        
        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(stop_words='english')
        
        # Fit and transform the title and text
        tfidf_matrix = vectorizer.fit_transform([title, text])
        
        # Calculate cosine similarity
        similarity = (tfidf_matrix * tfidf_matrix.T).A[0][1]
        
        # Lower threshold for relevance (was 0.3)
        return similarity > 0.1
        
    except Exception as e:
        logger.error(f"Error checking content relevance: {e}")
        return True  # On error, assume content is relevant

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
            
            # Add supported content types
            self.supported_content_types = {
                'text/html': self._process_html,
                'application/pdf': self._process_pdf,
                'application/x-pdf': self._process_pdf,
                'application/octet-stream': self._check_and_process_pdf,
                'binary/octet-stream': self._check_and_process_pdf
            }
            
            # Initialize content type statistics
            if 'content_type_stats' not in globals():
                global content_type_stats
                content_type_stats = {
                    'html': {'attempts': 0, 'successes': 0, 'failures': 0},
                    'pdf': {'attempts': 0, 'successes': 0, 'failures': 0},
                    'unknown': {'attempts': 0, 'successes': 0, 'failures': 0}
                }
            
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
            existing_doc = self.collection.find_one({"url": result.url}) or {}
            current_time = datetime.now(UTC)
            
            # Get existing metadata safely
            existing_metadata = existing_doc.get("metadata", {})
            existing_crawl_meta = existing_metadata.get("crawl_meta", {})
            
            # Prepare metadata
            crawl_meta = {
                "method": str(result.method) if hasattr(result.method, '__name__') else str(result.method),
                "crawl_time": current_time,
                "updated_at": current_time,
                "content_hash": self._get_url_hash(result.text),
                "word_count": len(result.text.split()),
                "status": "success",
                "attempts": existing_crawl_meta.get("attempts", 0) + 1,
                "last_success": current_time,
                "last_failure": existing_crawl_meta.get("last_failure"),
                "failure_reason": None
            }
            
            # Prepare document for MongoDB
            document = {
                "url": result.url,
                "title": result.title or "",
                "text": result.text,
                "metadata": {
                    "source_meta": result.metadata or {},
                    "crawl_meta": crawl_meta
                },
                "method": str(result.method) if hasattr(result.method, '__name__') else str(result.method),
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
            existing_doc = self.collection.find_one({"url": url}) or {}
            current_time = datetime.now(UTC)
            
            # Get existing metadata safely
            existing_metadata = existing_doc.get("metadata", {})
            existing_crawl_meta = existing_metadata.get("crawl_meta", {})
            
            # Prepare metadata
            crawl_meta = {
                "method": "failed",
                "crawl_time": current_time,
                "updated_at": current_time,
                "content_hash": None,
                "word_count": 0,
                "status": "failed",
                "attempts": existing_crawl_meta.get("attempts", 0) + 1,
                "last_success": existing_crawl_meta.get("last_success"),
                "last_failure": current_time,
                "failure_reason": str(reason)
            }
            
            tracking_data = {
                "url": url,
                "title": "",
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
                "content_hash": ""
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
            ("BeautifulSoup Static", self._static_crawl, "static"),
            ("Playwright Dynamic", self._js_crawl, "javascript"),
            ("Selenium Fallback", self._selenium_crawl, "selenium"),
            ("Scrapy Fallback", self._scrapy_crawl, "scrapy")
        ]

        # Try each free crawler first
        for crawler_name, crawler_method, method_key in free_crawlers:
            logger.info(f"Attempting {crawler_name} crawler for: {url}")
            try:
                # Update attempt count
                if 'crawler_stats' in globals():
                    crawler_stats[method_key]['attempts'] += 1
                
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
            # Update Apify attempt count
            if 'crawler_stats' in globals():
                crawler_stats['apify']['attempts'] += 1
            
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
        """Enhanced static crawler with PDF support"""
        try:
            logger.info(f"Attempting static crawl for: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
            response = requests.get(url, headers=headers, timeout=10)
            
            # Handle common error codes
            if response.status_code == 403:
                logger.warning(f"Access forbidden (403) for {url}. Site may be blocking crawlers.")
                return None
            elif response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}. Adding longer delay.")
                time.sleep(random.uniform(5, 10))
                return None
            elif response.status_code != 200:
                logger.warning(f"Unexpected status code {response.status_code} for {url}")
                return None
                
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower().split(';')[0]
            
            # Process content based on type
            for supported_type, processor in self.supported_content_types.items():
                if supported_type in content_type:
                    result = processor(response.content, url)
                    if result:
                        return result
            
            # Default HTML processing
            if 'text/html' in content_type:
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
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Static crawler failed for {url}: {e}")
            return None
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
            
            # First try with default memory
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlingDepth": 1,
                "maxPagesPerCrawl": 1,
                "additionalMimeTypes": ["text/markdown", "text/plain"],
                "proxyConfiguration": {"useApifyProxy": True}
            }
            
            try:
                run = self.apify_client.actor("apify/website-content-crawler").call(run_input=run_input)
            except Exception as e:
                if "exceed the memory limit" in str(e):
                    logger.warning("Apify memory limit exceeded, trying with reduced memory")
                    # Try again with reduced memory
                    run_input["memoryMbytes"] = 4096  # Reduce memory to 4GB
                    run = self.apify_client.actor("apify/website-content-crawler").call(run_input=run_input)
                else:
                    raise
            
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

    def _process_pdf(self, content: bytes, url: str) -> Optional[CrawlResult]:
        """Process PDF content and extract text"""
        try:
            logger.info(f"Processing PDF content from {url}")
            content_type_stats['pdf']['attempts'] += 1
            
            # Try PyPDF2 first
            try:
                pdf_file = io.BytesIO(content)
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                if text.strip():
                    content_type_stats['pdf']['successes'] += 1
                    return self._create_result(url, text, "pdf_pypdf2")
            except Exception as e:
                logger.warning(f"PyPDF2 extraction failed for {url}, trying PDFMiner: {e}")

            # Fallback to PDFMiner
            try:
                resource_manager = PDFResourceManager()
                fake_file_handle = io.StringIO()
                converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
                page_interpreter = PDFPageInterpreter(resource_manager, converter)
                
                pdf_file = io.BytesIO(content)
                for page in PDFPage.get_pages(pdf_file):
                    page_interpreter.process_page(page)
                
                text = fake_file_handle.getvalue()
                converter.close()
                fake_file_handle.close()
                
                if text.strip():
                    content_type_stats['pdf']['successes'] += 1
                    return self._create_result(url, text, "pdf_pdfminer")
                
            except Exception as e:
                logger.error(f"PDFMiner extraction failed for {url}: {e}")
                content_type_stats['pdf']['failures'] += 1
                return None

        except Exception as e:
            logger.error(f"PDF processing failed for {url}: {e}")
            content_type_stats['pdf']['failures'] += 1
            return None

    def _check_and_process_pdf(self, content: bytes, url: str) -> Optional[CrawlResult]:
        """Check if content is PDF and process accordingly"""
        # Check for PDF signature (%PDF-)
        if content.startswith(b'%PDF-'):
            logger.info(f"Detected PDF content for {url}")
            return self._process_pdf(content, url)
        logger.warning(f"Content for {url} is not a valid PDF")
        content_type_stats['unknown']['attempts'] += 1
        content_type_stats['unknown']['failures'] += 1
        return None

    def _create_result(self, url: str, text: str, method: str) -> CrawlResult:
        """Create a CrawlResult object with extracted text"""
        # Try to extract title from first line or use URL
        title = text.strip().split('\n')[0][:100] if text else None
        
        return CrawlResult(
            url=url,
            title=title,
            text=text,
            metadata={
                'content_type': 'application/pdf',
                'extraction_method': method
            },
            crawl_time=datetime.now(UTC),
            method=method
        )

    def _process_html(self, content: bytes, url: str) -> Optional[CrawlResult]:
        """Process HTML content"""
        try:
            content_type_stats['html']['attempts'] += 1
            soup = BeautifulSoup(content.decode('utf-8', errors='ignore'), "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            
            if not text:
                content_type_stats['html']['failures'] += 1
                return None
                
            content_type_stats['html']['successes'] += 1
            return CrawlResult(
                url=url,
                title=soup.title.string if soup.title else None,
                text=text,
                metadata=self._extract_metadata(soup),
                crawl_time=datetime.now(UTC),
                method="static"
            )
        except Exception as e:
            logger.error(f"HTML processing failed: {e}")
            content_type_stats['html']['failures'] += 1
            return None

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
    
    # Initialize crawler statistics
    global crawler_stats, content_type_stats
    crawler_stats = {
        'static': {'attempts': 0, 'successes': 0, 'failures': 0},
        'javascript': {'attempts': 0, 'successes': 0, 'failures': 0},
        'selenium': {'attempts': 0, 'successes': 0, 'failures': 0},
        'scrapy': {'attempts': 0, 'successes': 0, 'failures': 0},
        'apify': {'attempts': 0, 'successes': 0, 'failures': 0}
    }
    
    content_type_stats = {
        'html': {'attempts': 0, 'successes': 0, 'failures': 0},
        'pdf': {'attempts': 0, 'successes': 0, 'failures': 0},
        'unknown': {'attempts': 0, 'successes': 0, 'failures': 0}
    }
    
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
    skipped_urls = 0
    cached_urls = 0
    
    for index, url in enumerate(urls, 1):
        logger.info(f"Processing URL {index}/{total_urls}: {url}")
        
        if not url:
            logger.warning("Skipping empty URL")
            skipped_urls += 1
            continue
            
        try:
            # Check if URL should be crawled
            should_crawl, existing_data = crawler.should_crawl(url)
            if not should_crawl and existing_data:
                cached_urls += 1
                successful_crawls += 1
                logger.info(f"Using cached data for {url}")
                continue

            result = crawler.crawl_url(url)
            if result:
                successful_crawls += 1
                logger.info(f"Successfully processed {url}")
                logger.info(f"Method: {result.method}")
                logger.info(f"Title: {result.title}")
                logger.info(f"Content length: {len(result.text)} characters")
                
                # Update crawler statistics
                if result.method in crawler_stats:
                    crawler_stats[result.method]['successes'] += 1
                crawler.verify_storage(url)
            else:
                # Update statistics for failed attempts
                for method in crawler_stats:
                    crawler_stats[method]['attempts'] += 1
                    crawler_stats[method]['failures'] += 1
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            continue
    
    # Calculate success rates
    success_rates = {}
    for method, stats in crawler_stats.items():
        total_attempts = stats['attempts']
        if total_attempts > 0:
            success_rate = (stats['successes'] / total_attempts) * 100
        else:
            success_rate = 0
        success_rates[method] = success_rate
    
    content_success_rates = {}
    for content_type, stats in content_type_stats.items():
        total_attempts = stats['attempts']
        if total_attempts > 0:
            success_rate = (stats['successes'] / total_attempts) * 100
        else:
            success_rate = 0
        content_success_rates[content_type] = success_rate
    
    # Log detailed summary
    logger.info("\n=== Crawl Summary ===")
    logger.info(f"Total URLs processed: {total_urls}")
    logger.info(f"Successfully crawled: {successful_crawls}")
    logger.info(f"Failed crawls: {total_urls - successful_crawls}")
    logger.info(f"Skipped URLs: {skipped_urls}")
    logger.info(f"Used cached data: {cached_urls}")
    
    logger.info("\n=== Crawler Performance ===")
    for method, stats in crawler_stats.items():
        if stats['attempts'] > 0:
            logger.info(f"\n{method.capitalize()} Crawler:")
            logger.info(f"  Attempts: {stats['attempts']}")
            logger.info(f"  Successes: {stats['successes']}")
            logger.info(f"  Failures: {stats['failures']}")
            logger.info(f"  Success Rate: {success_rates[method]:.1f}%")
    
    logger.info("\n=== Content Type Performance ===")
    for content_type, stats in content_type_stats.items():
        if stats['attempts'] > 0:
            logger.info(f"\n{content_type.upper()} Content:")
            logger.info(f"  Attempts: {stats['attempts']}")
            logger.info(f"  Successes: {stats['successes']}")
            logger.info(f"  Failures: {stats['failures']}")
            logger.info(f"  Success Rate: {content_success_rates[content_type]:.1f}%")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCrawling interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Crawling process completed")
