# scripts/config.py
import os
from dotenv import load_dotenv

# Load environment variables from secrets/.env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'secrets', '.env'))

# Add Perplexity configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "your_perplexity_api_key")
API_CHOICE = os.getenv("API_CHOICE", "openai")  # Options: 'openai' or 'perplexity'

# Hugging Face Configuration
HF_CONFIG = {
    'API_TOKENS': {
        'INFERENCE': os.getenv('HF_INFERENCE_TOKEN'),
        'MODEL_MGMT': os.getenv('HF_MODEL_MGMT_TOKEN'),
        'REPO': os.getenv('HF_REPO_TOKEN')
    },
    'DEFAULT_MODELS': {
        'SUMMARIZER': 'facebook/bart-large-cnn',
        'CLASSIFIER': 'distilbert-base-uncased',
        'SENTIMENT': 'nlptown/bert-base-multilingual-uncased-sentiment'
    },
    'MAX_LENGTH': 130,
    'MIN_LENGTH': 30,
    'DEFAULT_BATCH_SIZE': 10
}

# MongoDB Configuration
MONGO_CONFIG = {
    'MONGO_DB_URL': os.getenv('MONGO_DB_URL'),
    'MONGODB_DB_NAME1': os.getenv('MONGODB_DB_NAME1'),
    'MONGODB_DB_NAME2': os.getenv('MONGODB_DB_NAME2')
}

# OpenAI Configuration
OPENAI_CONFIG = {
    'API_KEY': os.getenv('OPENAI_API_KEY'),
    'MODEL': 'gpt-4-1106-preview',
    'ASSISTANTS': {
        'CLEANTEXT_ASSISTANT_ID': os.getenv('CLEANTEXT_ASSISTANT_ID'),
        'PROCESS_ASSISTANT_ID': os.getenv('PROCESS_ASSISTANT_ID')
    }
}

# Validate required environment variables
def validate_config():
    required_vars = {
        'MONGO_DB_URL': MONGO_CONFIG['MONGO_DB_URL'],
        'MONGODB_DB_NAME1': MONGO_CONFIG['MONGODB_DB_NAME1'],
        'MONGODB_DB_NAME2': MONGO_CONFIG['MONGODB_DB_NAME2'],
        'OPENAI_API_KEY': OPENAI_CONFIG['API_KEY'],
        'CLEANTEXT_ASSISTANT_ID': OPENAI_CONFIG['ASSISTANTS']['CLEANTEXT_ASSISTANT_ID'],
        'PROCESS_ASSISTANT_ID': OPENAI_CONFIG['ASSISTANTS']['PROCESS_ASSISTANT_ID'],
        'HF_INFERENCE_TOKEN': HF_CONFIG['API_TOKENS']['INFERENCE'],
        'HF_MODEL_MGMT_TOKEN': HF_CONFIG['API_TOKENS']['MODEL_MGMT']
        # HF_REPO_TOKEN is optional
    }
    
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Call validation on import
validate_config() 