# scripts/config.py
import os
from dotenv import load_dotenv

# Load environment variables from secrets/.env
load_dotenv(dotenv_path="secrets/.env")

# Now retrieve environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY")
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb://localhost:27017/")

# Assistant IDs
ASST_FOR_STORAGE = os.getenv("ASST_FOR_STORAGE", "default_storage_assistant_id")
ASST_FOR_WRITING = os.getenv("ASST_FOR_WRITING", "default_writing_assistant_id")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "your_vector_store_id")

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "your_api_key_here")












