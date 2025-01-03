from urllib.parse import urlparse
from datetime import datetime, UTC, timedelta
import hashlib

class MultiCrawler:
    def __init__(self, apify_api_key: str, mongodb_uri: str):
        self.apify_client = ApifyClient(apify_api_key)
        self.mongo_client = MongoClient(mongodb_uri)
        self.db = self.mongo_client['searchresults']
        self.collection = self.db['scraped_data']
        self.url_tracking = self.db['url_tracking']  # New collection for URL tracking
        
        # Create indexes
        self._setup_indexes()
        self._verify_connections()

    def _setup_indexes(self):
        """Setup necessary database indexes"""
        # Index for URL tracking
        self.url_tracking.create_index([("url", 1)], unique=True)
        self.url_tracking.create_index([("last_crawl_date", 1)])
        
        # Index for scraped data
        self.collection.create_index([("url", 1)])
        self.collection.create_index([("crawl_time", 1)])

    def _get_url_hash(self, content: str) -> str:
        """Generate hash of content to detect changes"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def _check_last_modified(self, url: str) -> Optional[datetime]:
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
            # Check URL tracking collection
            tracking_info = self.url_tracking.find_one({"url": url})
            
            if not tracking_info:
                logger.info(f"URL {url} has never been crawled")
                return True, None
            
            last_crawl_date = tracking_info['last_crawl_date']
            
            # Check if minimum crawl interval has passed (default: 7 days)
            min_interval = timedelta(days=7)
            if datetime.now(UTC) - last_crawl_date < min_interval:
                logger.info(f"URL {url} was recently crawled")
                
                # Get existing data
                existing_data = self.collection.find_one({
                    "url": url,
                    "crawl_time": last_crawl_date
                })
                return False, existing_data
            
            # Check if content has been modified
            last_modified = self._check_last_modified(url)
            
            if last_modified and last_modified <= last_crawl_date:
                logger.info(f"Content for {url} hasn't changed since last crawl")
                
                # Get existing data
                existing_data = self.collection.find_one({
                    "url": url,
                    "crawl_time": last_crawl_date
                })
                return False, existing_data
            
            logger.info(f"Content for {url} needs to be recrawled")
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking crawl status for {url}: {e}")
            return True, None  # Crawl on error to be safe

    def _update_url_tracking(self, url: str, result: CrawlResult):
        """Update URL tracking information"""
        tracking_data = {
            "url": url,
            "last_crawl_date": result.crawl_time,
            "last_crawl_method": result.method,
            "content_hash": self._get_url_hash(result.text),
            "title": result.title,
            "success": True
        }
        
        self.url_tracking.update_one(
            {"url": url},
            {"$set": tracking_data},
            upsert=True
        )

    def _record_crawl_failure(self, url: str):
        """Record failed crawl attempt"""
        tracking_data = {
            "url": url,
            "last_attempt_date": datetime.now(UTC),
            "success": False
        }
        
        self.url_tracking.update_one(
            {"url": url},
            {"$set": tracking_data},
            upsert=True
        )

    def crawl_url(self, url: str) -> Optional[CrawlResult]:
        """Try different crawling methods with fallback"""
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

        # Try each crawling method
        for crawler_method in [self._static_crawl, self._js_crawl, self._apify_crawl]:
            result = crawler_method(url)
            if result and len(result.text) > 100:
                logger.info(f"Successful crawl with {result.method} for {url}")
                self._store_result(result)
                self._update_url_tracking(url, result)
                return result

        logger.error(f"All crawling methods failed for: {url}")
        self._record_crawl_failure(url)
        return None

def main():
    # ... (previous main code remains the same)
    
    # Process URLs
    for url in urls:
        result = crawler.crawl_url(url)
        if result:
            logger.info(f"Successfully processed {url} using {result.method} method")
            logger.info(f"Content length: {len(result.text)} characters")
        else:
            logger.error(f"Failed to process {url}")
