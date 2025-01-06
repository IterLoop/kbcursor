import logging
from datetime import datetime, UTC
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base.base_crawler import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)

class JSCrawler(BaseCrawler):
    """JavaScript-enabled crawler using Playwright with proxy support"""
    
    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def crawl(self, url: str) -> Optional[CrawlResult]:
        browser = None
        try:
            logger.info(f"Attempting JavaScript crawl for: {url}")
            
            # Get proxy
            proxy = self._get_proxy()
            
            with sync_playwright() as p:
                # Setup browser arguments
                browser_args = []
                if proxy:
                    logger.info(f"Using proxy: {proxy}")
                    browser_args.append(f'--proxy-server={proxy}')
                
                # Launch browser
                browser = p.chromium.launch(
                    headless=True,
                    args=browser_args
                )
                
                # Create context and page
                context = browser.new_context(user_agent=self.user_agent)
                page = context.new_page()
                page.set_default_timeout(30000)
                
                # Navigate and wait for content
                page.goto(url, wait_until="networkidle")
                
                # Wait for common content selectors
                selectors = ["article", "main", ".content", "#content"]
                for selector in selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                    except:
                        continue
                
                # Get content
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                
                if not text:
                    logger.warning(f"No text content found for {url}")
                    return None
                
                # Create result
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
            if proxy:
                self._mark_proxy_failed(proxy)
            return None
            
        finally:
            if browser:
                browser.close() 