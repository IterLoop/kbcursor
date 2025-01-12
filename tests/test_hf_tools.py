import unittest
from unittest.mock import patch, MagicMock
from tools.hf_tools import HFTools

class TestHFTools(unittest.TestCase):
    """Test cases for HuggingFace Tools implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.hf_tools = HFTools()
        self.test_text = "This is a test text for processing. It contains multiple sentences and should be suitable for testing various NLP tasks."
    
    @patch('tools.hf_tools.pipeline')
    def test_summarize_text(self, mock_pipeline):
        """Test text summarization"""
        # Mock the summarizer pipeline
        mock_summarizer = MagicMock()
        mock_summarizer.return_value = [{'summary_text': 'Test summary'}]
        mock_pipeline.return_value = mock_summarizer
        
        # Create new instance with mocked pipeline
        tools = HFTools()
        
        # Test summarization
        summary = tools.summarize_text(self.test_text)
        self.assertEqual(summary, 'Test summary')
        
        # Test error handling
        mock_summarizer.side_effect = Exception("Test error")
        summary = tools.summarize_text(self.test_text)
        self.assertEqual(summary, "")
    
    @patch('tools.hf_tools.pipeline')
    def test_classify_text(self, mock_pipeline):
        """Test text classification"""
        # Mock the classifier pipeline
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{'label': 'positive', 'score': 0.95}]
        mock_pipeline.return_value = mock_classifier
        
        # Create new instance with mocked pipeline
        tools = HFTools()
        
        # Test classification without labels
        result = tools.classify_text(self.test_text)
        self.assertEqual(result['label'], 'positive')
        self.assertEqual(result['score'], 0.95)
        
        # Test classification with custom labels
        labels = ['tech', 'sports', 'politics']
        result = tools.classify_text(self.test_text, labels=labels)
        self.assertEqual(result['label'], 'positive')
        self.assertEqual(result['score'], 0.95)
        
        # Test error handling
        mock_classifier.side_effect = Exception("Test error")
        result = tools.classify_text(self.test_text)
        self.assertEqual(result['label'], 'error')
        self.assertEqual(result['score'], 0.0)
    
    @patch('tools.hf_tools.pipeline')
    def test_analyze_sentiment(self, mock_pipeline):
        """Test sentiment analysis"""
        # Mock the sentiment analyzer pipeline
        mock_analyzer = MagicMock()
        mock_analyzer.return_value = [{'label': 'POSITIVE', 'score': 0.9}]
        mock_pipeline.return_value = mock_analyzer
        
        # Create new instance with mocked pipeline
        tools = HFTools()
        
        # Test sentiment analysis
        result = tools.analyze_sentiment(self.test_text)
        self.assertEqual(result['sentiment'], 'POSITIVE')
        self.assertEqual(result['score'], 0.9)
        
        # Test error handling
        mock_analyzer.side_effect = Exception("Test error")
        result = tools.analyze_sentiment(self.test_text)
        self.assertEqual(result['sentiment'], 'error')
        self.assertEqual(result['score'], 0.0)

if __name__ == '__main__':
    unittest.main() 