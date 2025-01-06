"""Initialize MongoDB database structure."""
import os
from pathlib import Path
import logging
from dotenv import load_dotenv
from tools.mongo import MongoManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables"""
    ROOT_DIR = Path(__file__).parent.parent
    env_path = ROOT_DIR / 'secrets' / '.env'
    
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found at {env_path}")
    
    load_dotenv(env_path)
    
    required_vars = ['MONGO_DB_URL', 'MONGODB_DB_NAME1', 'MONGODB_DB_NAME2']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def main():
    """Initialize MongoDB database structure"""
    try:
        # Setup environment
        setup_environment()
        
        # Initialize database manager
        mongo_manager = MongoManager()
        
        try:
            # Initialize databases
            mongo_manager.init_search_db()
            mongo_manager.init_content_db()
            
            # Verify structure
            mongo_manager.verify_database_structure()
            
            logger.info("\nDatabase initialization completed successfully!")
            
        finally:
            mongo_manager.close()
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    main() 