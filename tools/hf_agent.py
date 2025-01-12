from transformers import pipeline
import logging
from typing import List, Dict, Any, Optional
from .hf_tools import HFTools

class HFAgentManager:
    def __init__(self):
        """Initialize the HF Agent Manager with tools and pipelines"""
        self.logger = logging.getLogger(__name__)
        self.tools = HFTools()
        self._register_tools()
        
    def _register_tools(self):
        """Register available tools for text processing"""
        self.registered_tools = {
            'summarize': {
                'name': "summarize",
                'description': "Summarize input text",
                'function': self.tools.summarize_text
            },
            'classify': {
                'name': "classify",
                'description': "Classify input text",
                'function': self.tools.classify_text
            },
            'sentiment': {
                'name': "sentiment",
                'description': "Analyze sentiment of input text",
                'function': self.tools.analyze_sentiment
            }
        }
        
    def process_content(self, content: str, task_type: str, **kwargs) -> Dict[str, Any]:
        """Process content using specified task type"""
        try:
            if task_type not in self.registered_tools:
                raise ValueError(f"Invalid task type: {task_type}")
                
            tool = self.registered_tools[task_type]
            result = tool['function'](content, **kwargs)
            return {"status": "success", "result": result}
            
        except Exception as e:
            self.logger.error(f"Error processing content with task {task_type}: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def batch_process(self, contents: List[str], task_type: str, batch_size: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Process multiple pieces of content in batches"""
        results = []
        for i in range(0, len(contents), batch_size):
            batch = contents[i:i + batch_size]
            batch_results = [self.process_content(content, task_type, **kwargs) for content in batch]
            results.extend(batch_results)
        return results 