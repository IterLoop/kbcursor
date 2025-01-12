import os
import pytest
from datetime import datetime, UTC
from tools.mongo import MongoDB
from tools.hf_agent import HFAgentManager
from tools.vector_db import VectorDB
from tools.youtube_transcript_api import YouTubeTranscriptAPI
from scripts.crawlers.strategies.static_crawler import StaticCrawler
from scripts.crawlers.strategies.selenium_crawler import SeleniumCrawler

@pytest.fixture(scope="session")
def env_setup():
    """Setup environment variables for testing."""
    return {
        'mongo_url': 'mongodb://localhost:27017',
        'db_name': 'ghostwriter_test',
        'hf_token': os.getenv('HF_TOKEN'),
        'apify_key': os.getenv('APIFY_KEY')
    }

@pytest.fixture(scope="session")
def mongo_db(env_setup):
    """Initialize MongoDB connection."""
    db = MongoDB(env_setup['mongo_url'], env_setup['db_name'])
    db.clear_test_data()  # Clear any existing test data
    return db

@pytest.fixture(scope="session")
def hf_agent():
    """Initialize Hugging Face Agent."""
    return HFAgentManager()

@pytest.fixture(scope="session")
def vector_db():
    """Initialize Vector Database."""
    db = VectorDB()
    db.clear_test_data()  # Clear any existing test data
    return db

class TestUserStories:
    """Test suite based on user stories from PRD."""
    
    def test_static_website_scraping(self, mongo_db):
        """Test: As a user, I want to scrape content from static websites."""
        # Setup test URL - using Python.org as it's reliable and static
        test_url = "https://www.python.org"
        
        # Initialize crawler
        crawler = StaticCrawler()
        
        # Scrape content
        content = crawler.scrape(test_url)
        
        # Verify content structure
        assert content is not None
        assert 'url' in content
        assert 'title' in content
        assert 'text' in content
        assert 'metadata' in content
        
    def test_dynamic_website_scraping(self, mongo_db):
        """Test: As a user, I want to scrape content from dynamic websites."""
        # Setup test URL - using GitHub as it's reliable and has dynamic content
        test_url = "https://github.com"
        
        # Initialize crawler
        crawler = SeleniumCrawler()
        
        # Scrape content
        content = crawler.scrape(test_url)
        
        # Verify dynamic content
        assert content is not None
        assert 'url' in content
        assert 'title' in content
        assert 'text' in content
        assert 'metadata' in content

    def test_content_summarization(self, hf_agent):
        """Test: As a user, I want to summarize/tag content."""
        # Create test content
        test_content = {
            'text': 'This is a test article about artificial intelligence and machine learning. ' 
                   'The technology is advancing rapidly and transforming various industries.',
            'title': 'AI and ML Advances',
            'url': 'https://test.com/ai-ml'
        }
        
        # Process content
        processed = hf_agent.process_content(test_content['text'], task_type='summarize')
        
        # Verify processing results
        assert processed is not None
        assert 'summary' in processed
        assert len(processed['summary']) > 0
        
    def test_duplicate_exclusion(self, mongo_db):
        """Test: As a user, I want the system to exclude duplicates."""
        # Create test content
        test_content = {
            'url': 'https://test.com/duplicate',
            'title': 'Test Duplicate Article',
            'text': 'Duplicate content test',
            'metadata': {
                'source': 'test',
                'crawl_time': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            },
            'content_hash': 'test_hash'
        }
        
        # First insertion
        first_id = mongo_db.store_raw_content(test_content)
        assert first_id is not None
        
        # Try to insert duplicate
        second_id = mongo_db.store_raw_content(test_content)
        assert second_id is None  # Should not insert duplicate
        
    def test_video_transcript_extraction(self):
        """Test: As a user, I want to extract video transcripts."""
        # Initialize YouTube transcript API
        yt_api = YouTubeTranscriptAPI()
        
        # Test video ID (using a TED Talk with available transcripts)
        test_video_id = "8jPQjjsBbIc"
        
        # Extract transcript
        transcript = yt_api.get_transcript(test_video_id)
        
        # Verify transcript
        assert transcript is not None
        assert 'text' in transcript
        assert 'language' in transcript
        assert len(transcript['text']) > 0
        
        # Test language detection
        available_languages = yt_api.get_available_languages(test_video_id)
        assert len(available_languages) > 0
        
        # Test translation (if available)
        if len(available_languages) > 1:
            translated = yt_api.translate_transcript(test_video_id, 'es')
            assert translated is not None
            assert translated['language'] == 'es'
            
    def test_vector_search(self, vector_db):
        """Test: As a user, I want to search through processed content."""
        # Add test documents
        test_docs = [
            {'text': 'Article about artificial intelligence', 'id': '1'},
            {'text': 'Document about machine learning', 'id': '2'},
            {'text': 'Paper on natural language processing', 'id': '3'}
        ]
        
        for doc in test_docs:
            vector_db.index_document(doc)
            
        # Search for similar documents
        query = "AI and machine learning"
        results = vector_db.search(query, k=2)
        
        # Verify search results
        assert len(results) > 0
        assert all('score' in doc for doc in results)
        assert all('id' in doc for doc in results)
        
    def test_export_functionality(self, mongo_db):
        """Test: As a user, I want to export processed data."""
        # Add test processed content
        test_content = {
            'text': 'Test processed content',
            'summary': 'Test summary',
            'processed_date': datetime.now(UTC).isoformat()
        }
        mongo_db.store_processed_content(test_content)
        
        # Export data
        export_data = mongo_db.export_processed_content()
        
        # Verify export structure
        assert isinstance(export_data, list)
        assert len(export_data) > 0
        assert all('text' in doc for doc in export_data)
        assert all('processed_date' in doc for doc in export_data)
        
    def test_end_to_end_pipeline(self, mongo_db, hf_agent, vector_db):
        """Test: End-to-end content processing pipeline."""
        # Create test content
        test_content = {
            'url': 'https://test.com/pipeline',
            'title': 'Test Pipeline Article',
            'text': 'Test content for pipeline verification. This article discusses AI and machine learning.',
            'metadata': {
                'source': 'test',
                'crawl_time': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            },
            'content_hash': 'pipeline_test_hash'
        }
        
        # 1. Store raw content
        raw_id = mongo_db.store_raw_content(test_content)
        assert raw_id is not None
        
        # 2. Process content
        processed = hf_agent.process_content(test_content['text'], task_type='summarize')
        assert processed is not None
        
        # 3. Store processed content
        processed['original_id'] = raw_id
        processed['processed_date'] = datetime.now(UTC).isoformat()
        proc_id = mongo_db.store_processed_content(processed)
        assert proc_id is not None
        
        # 4. Index in vector database
        vector_db.index_document({
            'id': str(proc_id),
            'text': processed['summary']
        })
        
        # 5. Search for the content
        results = vector_db.search(test_content['text'], k=1)
        assert len(results) > 0
        assert results[0]['id'] == str(proc_id) 