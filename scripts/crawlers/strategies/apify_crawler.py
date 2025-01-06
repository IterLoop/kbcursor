import logging
from datetime import datetime, UTC
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from apify_client import ApifyClient

from ..base.base_crawler import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

class ApifyCrawler(BaseCrawler):
    """Apify-based crawler as a fallback option"""
    
    def __init__(self, apify_api_key: str):
        super().__init__()
        self.client = ApifyClient(apify_api_key)
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=4, max=30))
    def crawl(self, url: str) -> Optional[CrawlResult]:
        try:
            logger.info(f"Attempting Apify crawl for: {url}")
            
            # Setup crawl input
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlingDepth": 1,
                "maxPagesPerCrawl": 1,
                "additionalMimeTypes": ["text/markdown", "text/plain"],
                "proxyConfiguration": {"useApifyProxy": True}
            }
            
            # Run the crawler
            run = self.client.actor("apify/website-content-crawler").call(run_input=run_input)
            items = self.client.dataset(run["defaultDatasetId"]).list_items().items
            
            if not items:
                logger.warning(f"No content retrieved for {url}")
                return None
            
            # Process first item
            item = items[0]
            if not item.get('text'):
                logger.warning(f"No text content in response for {url}")
                return None
            
            # Create result
            result = CrawlResult(
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
            
            return result
            
        except Exception as e:
            logger.error(f"Apify crawler failed for {url}: {e}")
            return None 