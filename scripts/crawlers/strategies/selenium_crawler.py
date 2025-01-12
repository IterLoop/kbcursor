from datetime import datetime, UTC
from typing import Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base.base_crawler import BaseCrawler, CrawlResult
from ..base.browser_pool import BrowserPool
from logging import getLogger

logger = getLogger(__name__)

class SeleniumCrawler(BaseCrawler):
    """Selenium-based crawler implementation with browser pooling"""
    
    def __init__(self, proxy_manager=None, *, pool_size: int = 3):
        super().__init__(proxy_manager)
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.browser_pool = BrowserPool(size=pool_size)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def crawl(self, url: str) -> Optional[CrawlResult]:
        """Crawl a URL using Selenium with Chrome in headless mode"""
        try:
            logger.info(f"Attempting Selenium crawl for: {url}")
            
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--user-agent={self.user_agent}')
            
            # Add proxy if available
            proxy = self._get_proxy()
            if proxy:
                logger.info(f"Using proxy: {proxy}")
                chrome_options.add_argument(f'--proxy-server={proxy}')
            
            # Create and use webdriver
            with webdriver.Chrome(options=chrome_options) as driver:
                # Navigate to URL
                driver.get(url)
                
                # Wait for body to be present
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Get page content
                content = driver.page_source
                soup = BeautifulSoup(content, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                
                if not text:
                    logger.warning(f"No text content found for {url}")
                    return None
                
                # Create result
                result = CrawlResult(
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
                
                return result
                
        except Exception as e:
            logger.error(f"Selenium crawler failed for {url}: {e}")
            if proxy:
                self._mark_proxy_failed(proxy)
            return None 