"""Dynamic website crawler using Selenium."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, UTC
import hashlib
import logging
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SeleniumCrawler:
    """Crawler for dynamic websites using Selenium."""
    
    def __init__(self):
        """Initialize Selenium crawler with Chrome driver."""
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Initialize driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape content from a dynamic website.
        Returns structured content or None if scraping fails.
        """
        try:
            # Load page
            self.driver.get(url)
            
            # Wait for dynamic content
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Extract content
            title = self.driver.title
            
            # Get dynamic elements
            dynamic_elements = []
            for element in self.driver.find_elements(By.CSS_SELECTOR, '[data-dynamic], .dynamic-content'):
                dynamic_elements.append({
                    'type': element.tag_name,
                    'text': element.text,
                    'attributes': element.get_property('attributes')
                })
            
            # Get main text content
            text_elements = self.driver.find_elements(By.CSS_SELECTOR, 'p, article, section')
            text = " ".join([elem.text for elem in text_elements])
            
            # Calculate content hash
            content_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Get word count
            word_count = len(text.split())
            
            # Create metadata
            metadata = {
                'source_meta': {
                    'title_tag': title,
                    'meta_description': self.driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]').get_attribute('content') if self.driver.find_elements(By.CSS_SELECTOR, 'meta[name="description"]') else "",
                    'meta_keywords': self.driver.find_element(By.CSS_SELECTOR, 'meta[name="keywords"]').get_attribute('content') if self.driver.find_elements(By.CSS_SELECTOR, 'meta[name="keywords"]') else "",
                    'dynamic_elements': dynamic_elements
                },
                'crawl_meta': {
                    'method': 'selenium',
                    'crawl_time': datetime.now(UTC),
                    'updated_at': datetime.now(UTC),
                    'content_hash': content_hash,
                    'word_count': word_count,
                    'status': 'success',
                    'attempts': 1,
                    'last_success': datetime.now(UTC),
                    'last_failure': None,
                    'failure_reason': None
                }
            }
            
            # Structure content
            content = {
                'url': url,
                'title': title,
                'text': text,
                'metadata': metadata,
                'method': 'selenium',
                'crawl_time': datetime.now(UTC),
                'updated_at': datetime.now(UTC),
                'word_count': word_count,
                'status': 'success',
                'content_hash': content_hash,
                'dynamic_elements': dynamic_elements
            }
            
            return content
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None
            
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit() 