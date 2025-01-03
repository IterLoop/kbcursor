import logging
import os
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin
from scripts import scraper
from crawler.crawlers.static_crawler import StaticCrawler
from crawler.cleaner import TextCleaner
from crawler.base import WebContent
from bs4 import BeautifulSoup
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class URLCollector:
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.collected_urls: Set[str] = set()
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and matches our criteria"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except Exception:
            return False
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and query parameters"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def extract_urls_from_text(self, text: str, base_url: str) -> Set[str]:
        """Extract URLs from text content"""
        soup = BeautifulSoup(text, 'html.parser')
        urls = set()
        
        # Find all links
        for link in soup.find_all('a', href=True):
            url = link['href']
            # Convert relative URLs to absolute
            if not bool(urlparse(url).netloc):
                url = urljoin(base_url, url)
            
            if self.is_valid_url(url):
                urls.add(self.normalize_url(url))
        
        return urls
    
    def collect_urls_from_seed(self, seed_url: str, max_urls: int = 100) -> Set[str]:
        """Collect URLs starting from a seed URL"""
        if not self.is_valid_url(seed_url):
            logger.error(f"Invalid seed URL: {seed_url}")
            return set()
        
        self.collected_urls.add(seed_url)
        to_visit = {seed_url}
        
        while to_visit and len(self.collected_urls) < max_urls:
            current_url = to_visit.pop()
            if current_url in self.visited_urls:
                continue
                
            try:
                logger.info(f"Collecting URLs from: {current_url}")
                # Try static scraping first
                try:
                    content = scraper.scrape_static_page(current_url)
                except Exception:
                    content = scraper.scrape_js_page(current_url)
                
                # Extract new URLs
                new_urls = self.extract_urls_from_text(content, current_url)
                
                # Add new URLs to collection
                for url in new_urls:
                    if url not in self.visited_urls and len(self.collected_urls) < max_urls:
                        self.collected_urls.add(url)
                        to_visit.add(url)
                
            except Exception as e:
                logger.warning(f"Failed to collect URLs from {current_url}: {e}")
            
            self.visited_urls.add(current_url)
        
        return self.collected_urls

def create_web_content_from_text(url: str, text: str, source: str) -> WebContent:
    """Create WebContent object from scraped text"""
    soup = BeautifulSoup(text, 'html.parser')
    title = soup.title.string if soup.title else "Untitled"
    
    return WebContent(
        url=url,
        title=title,
        text=text,
        metadata={
            'extraction_method': source
        },
        source=source
    )

def crawl_with_fallback(url: str, api_key: str) -> Optional[WebContent]:
    """Attempt to crawl URL with multiple methods, falling back as needed"""
    
    # 1. Try static scraper first
    logger.info(f"Attempting static scrape for: {url}")
    try:
        text = scraper.scrape_static_page(url)
        if text.strip():
            logger.info("Static scrape successful")
            return create_web_content_from_text(url, text, "static_scraper")
    except Exception as e:
        logger.warning(f"Static scrape failed: {e}")
    
    # 2. Try JavaScript scraper
    logger.info(f"Static scrape failed, attempting JS scrape for: {url}")
    try:
        text = scraper.scrape_js_page(url)
        if text.strip():
            logger.info("JS scrape successful")
            return create_web_content_from_text(url, text, "js_scraper")
    except Exception as e:
        logger.warning(f"JS scrape failed: {e}")
    
    # 3. Finally, try Apify crawler as last resort
    logger.info(f"All scraping methods failed, attempting Apify crawler for: {url}")
    apify_crawler = ApifyCrawler(api_key)
    content = apify_crawler.crawl(url)
    if content and content.text.strip():
        logger.info("Apify crawler successful")
        return content
    
    logger.error(f"All extraction methods failed for: {url}")
    return None

def save_urls_to_file(urls: Set[str], filename: str):
    """Save collected URLs to a file"""
    with open(filename, 'w', encoding='utf-8') as f:
        for url in sorted(urls):
            f.write(f"{url}\n")

def main():
    # Configuration
    api_key = "apify_api_RqJ95dSauHAkMv1WGiajI2ysI8zAlg04FzoV"
    seed_url = "https://www.ibm.com/think/topics/ai-supply-chain"  # Example seed URL
    output_dir = "crawled_content"
    urls_file = "collected_urls.txt"
    max_urls = 50  # Maximum number of URLs to collect
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Step 1: Collect URLs using scraper
        logger.info(f"Starting URL collection from seed: {seed_url}")
        collector = URLCollector()
        collected_urls = collector.collect_urls_from_seed(seed_url, max_urls)
        
        # Save collected URLs
        save_urls_to_file(collected_urls, urls_file)
        logger.info(f"Collected {len(collected_urls)} URLs and saved to {urls_file}")
        
        # Initialize text cleaner
        cleaner = TextCleaner()
        
        # Step 2: Process each collected URL through the crawler pipeline
        for i, url in enumerate(collected_urls, 1):
            logger.info(f"Processing URL {i}/{len(collected_urls)}: {url}")
            
            # Attempt to get content with fallback mechanisms
            content = crawl_with_fallback(url, api_key)
            
            if content:
                # Convert to markdown with metadata
                markdown_content = cleaner.to_markdown(content)
                
                # Save to file
                output_file = os.path.join(output_dir, f"content_{i}.md")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                logger.info(f"Saved content to {output_file}")
            else:
                logger.error(f"Failed to extract content from {url}")
        
        logger.info("Processing completed!")
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Save intermediate generations to track progress
    os.makedirs('progress_logs', exist_ok=True)
    
    def save_progress(stage: str, message: str):
        with open(f'progress_logs/{stage}.txt', 'a', encoding='utf-8') as f:
            f.write(f'[{datetime.now().isoformat()}] {message}\n')
    
    try:
        save_progress('startup', 'Starting crawl process')
        main()
        save_progress('completion', 'Crawl completed successfully')
    except Exception as e:
        save_progress('error', f'Crawl failed with error: {str(e)}')
        raise