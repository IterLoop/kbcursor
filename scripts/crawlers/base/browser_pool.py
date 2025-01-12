from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from queue import Queue
import threading
from logging import getLogger

logger = getLogger(__name__)

class BrowserPool:
    def __init__(self, size: int = 3):
        self.size = size
        self.available = Queue()
        self.lock = threading.Lock()
        self._initialize_pool()

    def _create_browser(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        return webdriver.Chrome(options=chrome_options)

    def _initialize_pool(self):
        for _ in range(self.size):
            self.available.put(self._create_browser())

    def get_browser(self):
        return self.available.get()

    def return_browser(self, browser):
        try:
            self.available.put(browser)
        except:
            browser.quit()
            self.available.put(self._create_browser())

    def cleanup(self):
        with self.lock:
            while not self.available.empty():
                browser = self.available.get()
                browser.quit() 