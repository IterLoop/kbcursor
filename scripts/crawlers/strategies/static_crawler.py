import logging
from datetime import datetime, UTC
from typing import Optional
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base.base_crawler import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

class StaticCrawler(BaseCrawler):
    """Simple static page crawler using requests with proxy support"""
    
    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def crawl(self, url: str) -> Optional[CrawlResult]:
        try:
            logger.info(f"Attempting static crawl for: {url}")
            
            # Get proxy and setup request
            proxy = self._get_proxy()
            proxies = {'http': proxy, 'https': proxy} if proxy else None
            
            if proxies:
                logger.info(f"Using proxy: {proxy}")
            
            # Make request
            response = requests.get(
                url,
                headers=self.headers,
                proxies=proxies,
                timeout=10
            )
            response.raise_for_status()
            
            # Parse content
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            
            if not text:
                logger.warning(f"No text content found for {url}")
                return None
            
            # Create result
            result = CrawlResult(
                url=url,
                title=soup.title.string if soup.title else None,
                text=text,
                metadata=self._extract_metadata(soup),
                crawl_time=datetime.now(UTC),
                method="static"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Static crawler failed for {url}: {e}")
            if proxy:
                self._mark_proxy_failed(proxy)
            return None 