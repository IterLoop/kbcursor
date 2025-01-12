import unittest
from unittest.mock import patch, MagicMock
from tools.hf_agent import HFAgentManager

class TestHFAgentManager(unittest.TestCase):
    """Test cases for HuggingFace Agent Manager implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.hf_token = "test_token"
        with patch('tools.hf_agent.HfAgent'), \
             patch('tools.hf_agent.HFTools'):
            self.agent_manager = HFAgentManager(self.hf_token)
        
        self.test_text = "This is a test text for processing. It contains multiple sentences and should be suitable for testing various NLP tasks."
    
    def test_init(self):
        """Test initialization of HFAgentManager"""
        with patch('tools.hf_agent.HfAgent') as mock_agent, \
             patch('tools.hf_agent.HFTools') as mock_tools:
            
            agent_manager = HFAgentManager(self.hf_token)
            
            # Verify initialization
            mock_agent.assert_called_once()
            mock_tools.assert_called_once()
            self.assertEqual(agent_manager.hf_token, self.hf_token)
    
    def test_process_content_summarize(self):
        """Test content processing with summarization task"""
        # Mock the tools instance
        self.agent_manager.tools.summarize_text.return_value = "Test summary"
        
        # Test summarization
        result = self.agent_manager.process_content(
            self.test_text,
            task_type="summarize",
            max_length=100,
            min_length=30
        )
        
        self.assertEqual(result["task"], "summarize")
        self.assertEqual(result["result"], "Test summary")
        
        # Verify the tool was called with correct parameters
        self.agent_manager.tools.summarize_text.assert_called_with(
            self.test_text,
            max_length=100,
            min_length=30
        )
    
    def test_process_content_classify(self):
        """Test content processing with classification task"""
        # Mock the tools instance
        mock_classification = {"label": "test_label", "score": 0.95}
        self.agent_manager.tools.classify_text.return_value = mock_classification
        
        # Test classification
        labels = ["label1", "label2"]
        result = self.agent_manager.process_content(
            self.test_text,
            task_type="classify",
            labels=labels
        )
        
        self.assertEqual(result["task"], "classify")
        self.assertEqual(result["result"], mock_classification)
        
        # Verify the tool was called with correct parameters
        self.agent_manager.tools.classify_text.assert_called_with(
            self.test_text,
            labels=labels
        )
    
    def test_process_content_sentiment(self):
        """Test content processing with sentiment analysis task"""
        # Mock the tools instance
        mock_sentiment = {"sentiment": "POSITIVE", "score": 0.9}
        self.agent_manager.tools.analyze_sentiment.return_value = mock_sentiment
        
        # Test sentiment analysis
        result = self.agent_manager.process_content(
            self.test_text,
            task_type="sentiment"
        )
        
        self.assertEqual(result["task"], "sentiment")
        self.assertEqual(result["result"], mock_sentiment)
        
        # Verify the tool was called with correct parameters
        self.agent_manager.tools.analyze_sentiment.assert_called_with(self.test_text)
    
    def test_process_content_invalid_task(self):
        """Test content processing with invalid task type"""
        result = self.agent_manager.process_content(
            self.test_text,
            task_type="invalid_task"
        )
        
        self.assertEqual(result["task"], "invalid_task")
        self.assertIsNone(result["result"])
        self.assertIn("error", result)
    
    def test_batch_process(self):
        """Test batch processing of content"""
        # Mock the process_content method
        mock_result = {"task": "test", "result": "test_result"}
        self.agent_manager.process_content = MagicMock(return_value=mock_result)
        
        # Test batch processing
        contents = [self.test_text, self.test_text]
        results = self.agent_manager.batch_process(
            contents,
            task_type="test_task",
            extra_param="test"
        )
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], mock_result)
        self.assertEqual(results[1], mock_result)
        
        # Verify process_content was called correctly for each item
        self.assertEqual(
            self.agent_manager.process_content.call_count,
            len(contents)
        )

if __name__ == '__main__':
    unittest.main() 