# scripts/config.py
import os
from dotenv import load_dotenv

# Load environment variables from secrets/.env
load_dotenv(dotenv_path="secrets/.env")

# MongoDB Configuration
MONGO_DB_URL = os.getenv("MONGO_DB_URL", "mongodb://localhost:27017/")

# Database Names
SEARCH_DB = os.getenv("MONGODB_DB_NAME1", "search_data")
CONTENT_DB = os.getenv("MONGODB_DB_NAME2", "content_data")

# Collection Names
SEARCH_COLLECTION = "searches"
RAW_CONTENT_COLLECTION = "raw_content"
PROCESSED_CONTENT_COLLECTION = "processed_content"

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "your_api_key_here")
CLEANTEXT_ASSISTANT_ID = os.getenv("CLEANTEXT_ASSISTANT_ID", "your_assistant_id")












