import logging
from typing import Optional, List, Dict
from datetime import datetime, UTC, timedelta
import urllib.parse
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading

from .base.base_crawler import CrawlResult
from .strategies.selenium_crawler import SeleniumCrawler
from .strategies.js_crawler import JSCrawler
from .strategies.apify_crawler import ApifyCrawler
from ..utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

class MultiCrawler:
    """Orchestrates multiple crawling strategies with parallel processing"""
    
    def __init__(
        self,
        mongodb_url: str,
        serp_db_name: str,
        crawl_db_name: str,
        proxy_file_path: str,
        max_workers: int = 5,
        browser_pool_size: int = 3,
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
        
        # Initialize thread pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Initialize crawlers
        self.crawlers = [
            SeleniumCrawler(self.proxy_manager, pool_size=browser_pool_size),
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
            self.collection.create_index([("url", 1)], background=True)
            self.collection.create_index([("crawl_time", 1)], background=True)
            
            # Indexes for url_tracking collection
            try:
                self.url_tracking.create_index([("url", 1)], unique=True, background=True)
            except Exception as e:
                if not "already exists" in str(e):
                    raise
                
            try:
                self.url_tracking.create_index([("last_crawl_date", 1)], background=True)
            except Exception as e:
                if not "already exists" in str(e):
                    raise
            
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
            if not isinstance(last_crawl_date, datetime):
                last_crawl_date = datetime.fromisoformat(str(last_crawl_date))
            
            # Ensure both datetimes are timezone-aware
            if last_crawl_date.tzinfo is None:
                last_crawl_date = last_crawl_date.replace(tzinfo=UTC)
            
            min_interval = timedelta(days=7)
            current_time = datetime.now(UTC)
            
            if current_time - last_crawl_date < min_interval:
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
    
    def crawl_urls(self, search_results: List[Dict], search_term: str) -> None:
        """Crawl a list of URLs in parallel after filtering"""
        try:
            urls_to_crawl = []
            for result in search_results:
                url = result['url']
                should_crawl, existing_data = self.should_crawl(url)
                if should_crawl:
                    urls_to_crawl.append(result)
                elif existing_data:
                    logger.info(f"Using cached data for: {url}")
            
            logger.info(f"Found {len(urls_to_crawl)} URLs that need crawling")
            
            if not urls_to_crawl:
                return
            
            # Process URLs in parallel with progress bar
            with tqdm(total=len(urls_to_crawl), desc="Crawling URLs") as pbar:
                futures = []
                for result in urls_to_crawl:
                    future = self.executor.submit(self.crawl_url, result['url'])
                    futures.append(future)
                
                # Process results as they complete
                completed = 0
                while completed < len(futures):
                    try:
                        # Add timeout to make it interruptible
                        for future in as_completed(futures, timeout=1):
                            try:
                                crawl_result = future.result()
                                if crawl_result:
                                    crawl_result.search_term = search_term
                                    logger.info(f"Successfully crawled: {crawl_result.url}")
                                    logger.info(f"Method: {crawl_result.method}")
                                    logger.info(f"Title: {crawl_result.title}")
                                    logger.info(f"Content length: {len(crawl_result.text)} characters")
                                    
                                    # Store the result
                                    doc_id = self._store_result(crawl_result)
                                    logger.info(f"Stored document with ID: {doc_id}")
                                    
                                    self.successful_crawls += 1
                                else:
                                    self.failed_crawls += 1
                            except Exception as e:
                                logger.error(f"Error processing crawl result: {e}")
                                self.failed_crawls += 1
                            finally:
                                completed += 1
                                pbar.update(1)
                                futures.remove(future)
                    except TimeoutError:
                        # Check for interrupt
                        if threading.current_thread().is_alive():
                            continue
                        else:
                            break
                
        except KeyboardInterrupt:
            logger.info("\nInterrupt received, cleaning up...")
            # Cancel pending futures
            for future in futures:
                future.cancel()
            # Cleanup resources
            self.__del__()
            raise

        finally:
            logger.info("\nCrawling Summary:")
            logger.info(f"Successfully crawled: {self.successful_crawls}")
            logger.info(f"Failed crawls: {self.failed_crawls}")

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
                    return result
            except Exception as e:
                logger.error(f"{crawler.name} failed: {e}")
                continue

        # All crawlers failed
        logger.error(f"All crawling methods failed for: {url}")
        self._record_crawl_failure(url)
        return None

    def __del__(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        for crawler in self.crawlers:
            if hasattr(crawler, '__del__'):
                crawler.__del__() 