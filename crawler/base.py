from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WebContent:
    def __init__(self, 
                 url: str,
                 title: Optional[str] = None,
                 text: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 source: str = "unknown",
                 timestamp: Optional[datetime] = None):
        self.url = url
        self.title = title or "Untitled"
        self.text = text or ""
        self.metadata = metadata or {}
        self.source = source
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
            "source": self.source,
            "timestamp": self.timestamp.isoformat()
        }

class BaseCrawler:
    def __init__(self, name: str):
        self.name = name
    
    def crawl(self, url: str) -> Optional[WebContent]:
        """Base crawl method to be implemented by specific crawlers"""
        raise NotImplementedError
        
    def extract_metadata(self, soup) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object"""
        metadata = {}
        
        # Try to get OpenGraph metadata
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        for tag in og_tags:
            key = tag.get('property', '')[3:]  # Remove 'og:' prefix
            metadata[key] = tag.get('content', '')
            
        # Try to get standard metadata
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '')
            if name:
                metadata[name] = tag.get('content', '')
                
        # Try to get publication date
        pub_date = None
        date_meta = soup.find('meta', property='article:published_time')
        if date_meta:
            pub_date = date_meta.get('content')
        if not pub_date:
            date_meta = soup.find('meta', name='publication_date')
            if date_meta:
                pub_date = date_meta.get('content')
                
        if pub_date:
            metadata['published_date'] = pub_date
            
        return metadata 