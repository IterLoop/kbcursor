"""Hugging Face Agent Manager for text processing tasks."""

import logging
from typing import Dict, Any, Optional
from transformers import pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HFAgentManager:
    """Manages Hugging Face tools for text processing."""
    
    def __init__(self):
        """Initialize HF Agent Manager."""
        self.tools = {}
        self._initialize_tools()
        
    def _initialize_tools(self) -> None:
        """Initialize available tools."""
        try:
            self.tools['summarize'] = pipeline("summarization", model="facebook/bart-large-cnn")
            self.tools['classify'] = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
            self.tools['sentiment'] = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
            logger.info("Successfully initialized HF tools")
        except Exception as e:
            logger.error(f"Error initializing HF tools: {str(e)}")
            raise
    
    def process_content(self, text: str, task_type: str = 'summarize') -> Optional[Dict[str, Any]]:
        """Process content using specified task.
        
        Args:
            text: Text content to process
            task_type: Type of processing task ('summarize', 'classify', 'sentiment')
            
        Returns:
            Dictionary containing processed content or None if error
        """
        try:
            if task_type not in self.tools:
                logger.error(f"Unknown task type: {task_type}")
                return None
                
            tool = self.tools[task_type]
            result = tool(text)
            
            # Create base processed content
            processed = {
                'text': text,  # Original text
                'task_type': task_type,
                'status': 'success'
            }
            
            # Add task-specific results
            if task_type == 'summarize':
                processed['summary'] = result[0]['summary_text']
            elif task_type == 'classify':
                processed['classification'] = result[0]['label']
                processed['confidence'] = result[0]['score']
            elif task_type == 'sentiment':
                processed['sentiment'] = result[0]['label']
                processed['confidence'] = result[0]['score']
                
            logger.info(f"Successfully processed content with task: {task_type}")
            return processed
                
        except Exception as e:
            logger.error(f"Error processing content: {str(e)}")
            return None
    
    def batch_process(self, texts: list, task_type: str = 'summarize') -> list:
        """Process multiple pieces of content.
        
        Args:
            texts: List of text content to process
            task_type: Type of processing task
            
        Returns:
            List of processed content
        """
        return [self.process_content(text, task_type) for text in texts] 