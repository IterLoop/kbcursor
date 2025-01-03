from pymongo import MongoClient
import os

class Database:
    def __init__(self):
        self.client = MongoClient(os.getenv('MONGO_DB_URI', 'mongodb://localhost:27017/'))
        self.db = self.client['web_crawler']
        self.scraped_urls = self.db['scraped_urls']
    
    def url_exists(self, url: str) -> bool:
        """Check if URL has already been scraped"""
        return bool(self.scraped_urls.find_one({'url': url}))
    
    def add_url(self, url: str, metadata: dict = None):
        """Add URL to scraped collection"""
        if not self.url_exists(url):
            self.scraped_urls.insert_one({
                'url': url,
                'timestamp': datetime.now(),
                'metadata': metadata or {}
            })
    
    def get_all_scraped_urls(self):
        """Get all scraped URLs"""
        return [doc['url'] for doc in self.scraped_urls.find()] 