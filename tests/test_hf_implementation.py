import unittest
from unittest.mock import patch, MagicMock
from tools.hf_agent import HFAgentManager
from tools.hf_tools import HFTools

class TestHFImplementation(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.test_text = "This is a test text for processing."
        
        # Create mock pipelines
        self.mock_summarizer = MagicMock()
        self.mock_classifier = MagicMock()
        self.mock_sentiment = MagicMock()
        
        # Set up pipeline patch
        self.pipeline_patcher = patch('tools.hf_tools.pipeline')
        self.mock_pipeline = self.pipeline_patcher.start()
        
        def pipeline_side_effect(task, **kwargs):
            if task == "summarization":
                return self.mock_summarizer
            elif task == "zero-shot-classification":
                return self.mock_classifier
            elif task == "sentiment-analysis":
                return self.mock_sentiment
            return MagicMock()
            
        self.mock_pipeline.side_effect = pipeline_side_effect
        
        # Initialize agent manager
        self.agent_manager = HFAgentManager()
        
    def tearDown(self):
        """Clean up after tests"""
        self.pipeline_patcher.stop()
        
    def test_agent_initialization(self):
        """Test HFAgentManager initialization"""
        self.assertIsInstance(self.agent_manager.tools, HFTools)
        self.assertTrue(hasattr(self.agent_manager, 'registered_tools'))
        self.assertEqual(len(self.agent_manager.registered_tools), 3)  # summarize, classify, sentiment
        
    def test_summarization(self):
        """Test text summarization"""
        expected_summary = "Test summary"
        self.mock_summarizer.return_value = [{'summary_text': expected_summary}]
        
        result = self.agent_manager.process_content(
            self.test_text, 
            "summarize",
            max_length=100,
            min_length=30
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], expected_summary)
        self.mock_summarizer.assert_called_once_with(
            self.test_text,
            max_length=100,
            min_length=30
        )
        
    def test_classification(self):
        """Test text classification"""
        expected_classes = {"label": "test", "score": 0.9}
        self.mock_classifier.return_value = {
            'labels': [expected_classes['label']],
            'scores': [expected_classes['score']]
        }
        
        result = self.agent_manager.process_content(
            self.test_text,
            "classify",
            labels=["test", "other"]
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], expected_classes)
        self.mock_classifier.assert_called_once_with(
            self.test_text,
            ["test", "other"]
        )
        
    def test_sentiment_analysis(self):
        """Test sentiment analysis"""
        expected_sentiment = {"label": "positive", "score": 0.8}
        self.mock_sentiment.return_value = [{
            'label': expected_sentiment['label'].upper(),
            'score': expected_sentiment['score']
        }]
        
        result = self.agent_manager.process_content(
            self.test_text,
            "sentiment"
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], expected_sentiment)
        self.mock_sentiment.assert_called_once_with(self.test_text)
        
    def test_invalid_task(self):
        """Test handling of invalid task type"""
        result = self.agent_manager.process_content(
            self.test_text,
            "invalid_task"
        )
        
        self.assertEqual(result["status"], "error")
        self.assertIn("Invalid task type", result["message"])
        
    def test_batch_processing(self):
        """Test batch processing functionality"""
        texts = ["Text 1", "Text 2", "Text 3"]
        expected_summary = "Summary"
        self.mock_summarizer.return_value = [{'summary_text': expected_summary}]
        
        results = self.agent_manager.batch_process(
            texts,
            "summarize",
            batch_size=2
        )
        
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["result"], expected_summary)
        self.assertEqual(self.mock_summarizer.call_count, 3)

if __name__ == '__main__':
    unittest.main() 