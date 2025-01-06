import logging
from typing import Optional, List, Dict
from datetime import datetime, UTC, timedelta
import urllib.parse
from pymongo import MongoClient

from .base.base_crawler import CrawlResult
from .strategies.static_crawler import StaticCrawler
from .strategies.js_crawler import JSCrawler
from .strategies.apify_crawler import ApifyCrawler
from ..utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

class MultiCrawler:
    """Orchestrates multiple crawling strategies with fallback logic"""
    
    def __init__(
        self,
        mongodb_url: str,
        serp_db_name: str,
        crawl_db_name: str,
        proxy_file_path: str,
        apify_api_key: Optional[str] = None
    ):
        # Initialize MongoDB
        self.mongo_client = MongoClient(mongodb_url)
        self.serp_db = self.mongo_client[serp_db_name]
        self.crawl_db = self.mongo_client[crawl_db_name]
        self.collection = self.crawl_db['raw_content']
        self.url_tracking = self.crawl_db['url_tracking']
        
        # Initialize proxy manager
        self.proxy_manager = ProxyManager(proxy_file_path)
        
        # Initialize crawlers
        self.crawlers = [
            StaticCrawler(self.proxy_manager),
            JSCrawler(self.proxy_manager)
        ]
        
        # Add Apify crawler if API key provided
        if apify_api_key:
            self.crawlers.append(ApifyCrawler(apify_api_key))
        
        # Setup database indexes
        self._setup_indexes()
        
        # Statistics
        self.successful_crawls = 0
        self.failed_crawls = 0
    
    def _setup_indexes(self):
        """Setup necessary database indexes"""
        try:
            # Indexes for raw_content collection
            self.collection.create_index([("url", 1)])
            self.collection.create_index([("crawl_time", 1)])
            
            # Indexes for url_tracking collection
            self.url_tracking.create_index([("url", 1)], unique=True)
            self.url_tracking.create_index([("last_crawl_date", 1)])
            
            logger.info("MongoDB indexes verified")
            
        except Exception as e:
            logger.error(f"Index verification failed: {e}")
    
    def should_crawl(self, url: str) -> tuple[bool, Optional[dict]]:
        """Determine if URL should be crawled based on tracking data"""
        try:
            tracking_info = self.url_tracking.find_one({"url": url})
            
            if not tracking_info:
                return True, None
            
            last_crawl_date = tracking_info['last_crawl_date']
            min_interval = timedelta(days=7)
            
            if datetime.now(UTC) - last_crawl_date < min_interval:
                existing_data = self.collection.find_one({
                    "url": url,
                    "crawl_time": last_crawl_date
                })
                return False, existing_data
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking crawl status for {url}: {e}")
            return True, None
    
    def _store_result(self, result: CrawlResult) -> str:
        """Store crawl result in MongoDB"""
        try:
            document = {
                "url": result.url,
                "title": result.title,
                "text": result.text,
                "metadata": result.metadata,
                "crawl_time": result.crawl_time,
                "method": result.method,
                "search_term": result.search_term,
                "updated_at": datetime.now(UTC),
                "word_count": len(result.text.split())
            }
            
            # Update or insert document
            update_result = self.collection.update_one(
                {"url": result.url},
                {"$set": document},
                upsert=True
            )
            
            document_id = update_result.upserted_id or self.collection.find_one({"url": result.url})["_id"]
            
            # Update tracking
            self.url_tracking.update_one(
                {"url": result.url},
                {
                    "$set": {
                        "last_crawl_date": result.crawl_time,
                        "last_crawl_method": result.method,
                        "success": True,
                        "document_id": document_id,
                        "updated_at": datetime.now(UTC)
                    }
                },
                upsert=True
            )
            
            return str(document_id)
            
        except Exception as e:
            logger.error(f"Failed to store results for {result.url}: {e}")
            raise
    
    def _record_crawl_failure(self, url: str):
        """Record failed crawl attempt"""
        try:
            self.url_tracking.update_one(
                {"url": url},
                {
                    "$set": {
                        "last_attempt_date": datetime.now(UTC),
                        "success": False
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to record crawl failure for {url}: {e}")
    
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

        # Skip Google search URLs
        if 'google.com/search' in url:
            logger.warning(f"Skipping Google search URL: {url}")
            return None

        # Try each crawler
        for crawler in self.crawlers:
            logger.info(f"Attempting {crawler.name} for: {url}")
            try:
                result = crawler.crawl(url)
                if result and len(result.text) > 100:
                    logger.info(f"Successfully crawled with {crawler.name}")
                    try:
                        document_id = self._store_result(result)
                        logger.info(f"Stored result with ID: {document_id}")
                        self.successful_crawls += 1
                        return result
                    except Exception as e:
                        logger.error(f"Failed to store result: {e}")
                        continue
            except Exception as e:
                logger.error(f"{crawler.name} failed: {e}")
                continue

        # All crawlers failed
        logger.error(f"All crawling methods failed for: {url}")
        self._record_crawl_failure(url)
        self.failed_crawls += 1
        return None
    
    def crawl_urls(self, search_results: List[Dict], search_term: str) -> None:
        """Crawl a list of URLs after filtering"""
        urls_to_crawl = []
        for result in search_results:
            url = result['url']
            should_crawl, _ = self.should_crawl(url)
            if should_crawl:
                urls_to_crawl.append(result)
        
        logger.info(f"Found {len(urls_to_crawl)} URLs that need crawling")
        
        for idx, result in enumerate(urls_to_crawl, 1):
            url = result['url']
            logger.info(f"\nProcessing {idx}/{len(urls_to_crawl)}: {url}")
            
            try:
                crawl_result = self.crawl_url(url)
                if crawl_result:
                    crawl_result.search_term = search_term
                    logger.info(f"Successfully crawled: {url}")
                    logger.info(f"Method: {crawl_result.method}")
                    logger.info(f"Title: {crawl_result.title}")
                    logger.info(f"Content length: {len(crawl_result.text)} characters")
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                continue
        
        logger.info("\nCrawling Summary:")
        logger.info(f"Successfully crawled: {self.successful_crawls}")
        logger.info(f"Failed crawls: {self.failed_crawls}") 