import logging
from typing import Optional
from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import BaseCrawler, WebContent

logger = logging.getLogger(__name__)

class StaticCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("static")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def crawl(self, url: str) -> Optional[WebContent]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            return WebContent(
                url=url,
                title=soup.title.string if soup.title else None,
                text=soup.get_text(separator=" ", strip=True),
                metadata=self.extract_metadata(soup),
                source=self.name
            )
        except Exception as e:
            logger.error(f"Static crawler failed for {url}: {e}")
            return None

class JSCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("javascript")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def crawl(self, url: str) -> Optional[WebContent]:
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
                    source=self.name
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

class ApifyCrawler(BaseCrawler):
    def __init__(self, api_key: str):
        super().__init__("apify")
        self.client = ApifyClient(api_key)
        self.actor_id = "apify/website-content-crawler"
    
    def crawl(self, url: str) -> Optional[WebContent]:
        try:
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlingDepth": 1,
                "maxPagesPerCrawl": 1,
                "additionalMimeTypes": ["text/markdown", "text/plain"],
            }
            
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Get the first result
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
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
                    source=self.name
                )
            
            return None
        except Exception as e:
            logger.error(f"Apify crawler failed for {url}: {e}")
            return None 