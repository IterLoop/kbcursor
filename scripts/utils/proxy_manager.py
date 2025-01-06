import logging
from pathlib import Path
from typing import Optional, List
import requests
from fp.fp import FreeProxy

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, proxy_file_path: str):
        self.proxy_file_path = Path(proxy_file_path)
        self.proxy_list: List[str] = []
        self.current_index = -1
        self.failed_proxies = set()
        self._load_proxies()
    
    def _load_proxies(self) -> None:
        """Load proxies from file and validate format"""
        try:
            if not self.proxy_file_path.exists():
                logger.error(f"Proxy file not found: {self.proxy_file_path}")
                return

            with open(self.proxy_file_path, 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
            
            # Validate and format proxies
            self.proxy_list = [
                proxy if proxy.startswith(('http://', 'https://'))
                else f'http://{proxy}'
                for proxy in proxies
            ]
            logger.info(f"Loaded {len(self.proxy_list)} proxies")
            
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            self.proxy_list = []

    def get_next_proxy(self) -> Optional[str]:
        """Get next working proxy from rotation"""
        if not self.proxy_list:
            self._load_proxies()
            if not self.proxy_list:
                return None

        # Try all proxies until finding a working one
        attempts = 0
        while attempts < len(self.proxy_list):
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
            proxy = self.proxy_list[self.current_index]
            
            if proxy in self.failed_proxies:
                attempts += 1
                continue
                
            if self._test_proxy(proxy):
                return proxy
            
            self.failed_proxies.add(proxy)
            attempts += 1
        
        # If no working proxies found, try getting a new one from FreeProxy
        try:
            new_proxy = FreeProxy(rand=True).get()
            if new_proxy and self._test_proxy(new_proxy):
                self.proxy_list.append(new_proxy)
                return new_proxy
        except Exception as e:
            logger.error(f"Failed to get new proxy from FreeProxy: {e}")
        
        return None

    def _test_proxy(self, proxy: str, timeout: int = 5) -> bool:
        """Test if proxy is working"""
        try:
            response = requests.get(
                'https://www.google.com',
                proxies={'http': proxy, 'https': proxy},
                timeout=timeout
            )
            return response.status_code == 200
        except Exception:
            return False

    def mark_proxy_failed(self, proxy: str) -> None:
        """Mark a proxy as failed"""
        if proxy in self.proxy_list:
            self.failed_proxies.add(proxy)
            logger.info(f"Marked proxy as failed: {proxy}")

    def reset_failed_proxies(self) -> None:
        """Reset the list of failed proxies"""
        self.failed_proxies.clear()
        logger.info("Reset failed proxies list") 