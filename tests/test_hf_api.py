import unittest
from transformers import pipeline
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestHuggingFaceAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load environment variables and set up API token"""
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'secrets', '.env'))
        cls.api_token = os.getenv('HF_INFERENCE_TOKEN')
        if not cls.api_token:
            raise ValueError("HF_INFERENCE_TOKEN not found in environment variables")
            
    def test_pipeline_initialization(self):
        """Test if we can initialize a basic pipeline"""
        try:
            # Try to initialize a simple sentiment analysis pipeline
            classifier = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                token=self.api_token
            )
            logger.info("Successfully initialized sentiment analysis pipeline")
            
            # Test with a simple sentence
            test_text = "I love using Hugging Face transformers!"
            result = classifier(test_text)
            
            logger.info(f"API Test Result: {result}")
            
            # Basic assertions
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            self.assertIn('label', result[0])
            self.assertIn('score', result[0])
            
        except Exception as e:
            logger.error(f"Error testing Hugging Face API: {str(e)}")
            raise

if __name__ == '__main__':
    unittest.main() 