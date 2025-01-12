from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CrawlResult:
    url: str
    title: Optional[str]
    text: str
    metadata: Dict[str, Any]
    crawl_time: datetime
    method: str
    search_term: Optional[str] = None

class BaseCrawler(ABC):
    """Abstract base class for all crawlers"""
    
    def __init__(self, proxy_manager=None):
        self.proxy_manager = proxy_manager
        self.name = self.__class__.__name__
    
    @abstractmethod
    def crawl(self, url: str) -> Optional[CrawlResult]:
        """Implement the crawling logic in derived classes"""
        pass
    
    def _get_proxy(self) -> Optional[str]:
        """Get next available proxy if proxy manager exists"""
        if self.proxy_manager:
            return self.proxy_manager.get_next_proxy()
        return None
    
    def _mark_proxy_failed(self, proxy: str) -> None:
        """Mark a proxy as failed if proxy manager exists"""
        if self.proxy_manager and proxy:
            self.proxy_manager.mark_proxy_failed(proxy)
    
    @staticmethod
    def _extract_metadata(soup) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object"""
        metadata = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property'))
            content = meta.get('content')
            if name and content:
                metadata[name] = content
        return metadata 