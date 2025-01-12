import logging
import time
from typing import Dict, Any, List, Optional
from transformers import pipeline
from scripts.config import HF_CONFIG

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class HFTools:
    def __init__(self):
        """Initialize HF tools with required models"""
        logger.debug(f"Initializing HFTools with configuration: {HF_CONFIG}")
        
        try:
            # Initialize summarization pipeline
            logger.debug(f"Loading summarization model: {HF_CONFIG['DEFAULT_MODELS']['summarization']}")
            self.summarizer = pipeline(
                "summarization",
                model=HF_CONFIG['DEFAULT_MODELS']['summarization'],
                token=HF_CONFIG['API_TOKENS']['INFERENCE']
            )
            
            # Initialize classification pipeline
            logger.debug(f"Loading classification model: {HF_CONFIG['DEFAULT_MODELS']['classification']}")
            self.classifier = pipeline(
                "zero-shot-classification",
                model=HF_CONFIG['DEFAULT_MODELS']['classification'],
                token=HF_CONFIG['API_TOKENS']['INFERENCE']
            )
            
            # Initialize sentiment analysis pipeline
            logger.debug(f"Loading sentiment analysis model: {HF_CONFIG['DEFAULT_MODELS']['sentiment']}")
            self.sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model=HF_CONFIG['DEFAULT_MODELS']['sentiment'],
                token=HF_CONFIG['API_TOKENS']['INFERENCE']
            )
            
            logger.info("Successfully initialized Hugging Face tools with all models")
            
        except Exception as e:
            logger.error(f"Error initializing HF tools: {str(e)}")
            raise
            
    def summarize_text(self, text: str, max_length: Optional[int] = None, min_length: Optional[int] = None) -> str:
        """Summarize input text"""
        start_time = time.time()
        logger.debug(f"Starting text summarization. Text length: {len(text)}")
        
        try:
            # Use config defaults if not specified
            max_length = max_length or HF_CONFIG['MAX_LENGTH']
            min_length = min_length or HF_CONFIG['MIN_LENGTH']
            logger.debug(f"Using max_length={max_length}, min_length={min_length}")
            
            summary = self.summarizer(text, max_length=max_length, min_length=min_length)
            summary_text = summary[0]['summary_text']
            
            duration = time.time() - start_time
            logger.debug(f"Summarization completed in {duration:.2f} seconds. Summary length: {len(summary_text)}")
            
            return summary_text
            
        except Exception as e:
            logger.error(f"Error in summarization: {str(e)}\nInput text: {text[:100]}...")
            raise
            
    def classify_text(self, text: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Classify text into categories"""
        start_time = time.time()
        logger.debug(f"Starting text classification. Text length: {len(text)}, Labels: {labels}")
        
        try:
            # Use default labels if none provided
            if not labels:
                labels = ["positive", "negative", "neutral"]
            logger.debug(f"Using zero-shot classification with labels: {labels}")
            
            result = self.classifier(text, labels)
            
            # Format result to match test expectations
            classification = {
                "label": result['labels'][0],
                "score": result['scores'][0]
            }
            
            duration = time.time() - start_time
            logger.debug(f"Classification completed in {duration:.2f} seconds. Result: {classification}")
            
            return classification
            
        except Exception as e:
            logger.error(f"Error in classification: {str(e)}\nInput text: {text[:100]}...\nLabels: {labels}")
            return {"label": "error", "score": 0.0}
            
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of input text"""
        start_time = time.time()
        logger.debug(f"Starting sentiment analysis. Text length: {len(text)}")
        
        try:
            result = self.sentiment_analyzer(text)[0]
            
            # Format result to match test expectations
            sentiment = {
                "label": result['label'].lower(),
                "score": result['score']
            }
            
            duration = time.time() - start_time
            logger.debug(f"Sentiment analysis completed in {duration:.2f} seconds. Result: {result['label']}")
            
            return sentiment
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}\nInput text: {text[:100]}...")
            raise 