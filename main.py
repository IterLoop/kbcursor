import logging
import os
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from tenacity import retry, stop_after_attempt, wait_exponential

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImprovedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_url(self, url: str, timeout: int = 30) -> Optional[dict]:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            content = {
                'title': soup.title.string if soup.title else None,
                'text': soup.get_text(separator=' ', strip=True),
                'url': url
            }
            
            logger.info(f"Successfully scraped {url}")
            return content
            
        except requests.Timeout:
            logger.warning(f"Timeout while fetching {url}")
            raise
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {url}: {str(e)}")
            raise

    def process_urls(self, urls: list) -> list:
        results = []
        for url in urls:
            try:
                content = self.fetch_url(url)
                if content:
                    results.append(content)
            except Exception as e:
                logger.error(f"Failed to process {url}: {str(e)}")
                continue
        return results

def main():
    # Read URLs from file
    with open('collected_urls.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    scraper = ImprovedScraper()
    results = scraper.process_urls(urls)
    
    # Save results
    logger.info(f"Successfully scraped {len(results)} URLs")
    return results

if __name__ == "__main__":
    main()