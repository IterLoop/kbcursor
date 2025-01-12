"""Static website crawler implementation."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, UTC
import hashlib
import logging
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaticCrawler:
    """Crawler for static websites using requests and BeautifulSoup."""
    
    def __init__(self):
        """Initialize static crawler."""
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape content from a static website.
        Returns structured content or None if scraping fails.
        """
        try:
            # Fetch page
            response = self.session.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parse content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            title = soup.title.string if soup.title else ""
            text = " ".join([p.get_text() for p in soup.find_all(['p', 'article', 'section'])])
            
            # Calculate content hash
            content_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Get word count
            word_count = len(text.split())
            
            # Create metadata
            metadata = {
                'source_meta': {
                    'title_tag': title,
                    'meta_description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else "",
                    'meta_keywords': soup.find('meta', {'name': 'keywords'})['content'] if soup.find('meta', {'name': 'keywords'}) else ""
                },
                'crawl_meta': {
                    'method': 'static',
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
                'method': 'static',
                'crawl_time': datetime.now(UTC),
                'updated_at': datetime.now(UTC),
                'word_count': word_count,
                'status': 'success',
                'content_hash': content_hash
            }
            
            return content
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None
            
    def close(self):
        """Close the session."""
        self.session.close() 