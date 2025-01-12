import unittest
from unittest.mock import patch, MagicMock
from tools.hf_tools import HFTools

class TestHFTools(unittest.TestCase):
    """Test cases for HuggingFace Tools implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('transformers.pipeline') as mock_pipeline:
            self.hf_tools = HFTools()
            self.mock_pipeline = mock_pipeline
        
        self.test_text = "This is a test text for processing. It contains multiple sentences and should be suitable for testing various NLP tasks."
    
    def test_init(self):
        """Test initialization of HFTools"""
        with patch('transformers.pipeline') as mock_pipeline:
            hf_tools = HFTools()
            
            # Verify pipeline initialization
            self.assertEqual(mock_pipeline.call_count, 3)  # summarizer, classifier, sentiment
            
            # Verify attributes
            self.assertTrue(hasattr(hf_tools, 'summarizer'))
            self.assertTrue(hasattr(hf_tools, 'classifier'))
            self.assertTrue(hasattr(hf_tools, 'sentiment_analyzer'))
    
    def test_summarize_text(self):
        """Test text summarization"""
        # Mock the summarizer pipeline
        mock_summary = [{"summary_text": "Test summary"}]
        self.hf_tools.summarizer = MagicMock(return_value=mock_summary)
        
        # Test summarization with default parameters
        result = self.hf_tools.summarize_text(self.test_text)
        self.assertEqual(result, "Test summary")
        
        # Test summarization with custom parameters
        result = self.hf_tools.summarize_text(
            self.test_text,
            max_length=100,
            min_length=30
        )
        self.assertEqual(result, "Test summary")
        
        # Verify the pipeline was called with correct parameters
        self.hf_tools.summarizer.assert_called_with(
            self.test_text,
            max_length=100,
            min_length=30
        )
    
    def test_classify_text(self):
        """Test text classification"""
        # Mock the classifier pipeline
        mock_classification = [{"label": "test_label", "score": 0.95}]
        self.hf_tools.classifier = MagicMock(return_value=mock_classification)
        
        # Test classification with default labels
        result = self.hf_tools.classify_text(self.test_text)
        self.assertEqual(result["label"], "test_label")
        self.assertEqual(result["score"], 0.95)
        
        # Test classification with custom labels
        labels = ["label1", "label2"]
        result = self.hf_tools.classify_text(self.test_text, labels=labels)
        self.assertEqual(result["label"], "test_label")
        self.assertEqual(result["score"], 0.95)
        
        # Verify the pipeline was called with correct parameters
        self.hf_tools.classifier.assert_called_with(
            self.test_text,
            candidate_labels=labels
        )
    
    def test_analyze_sentiment(self):
        """Test sentiment analysis"""
        # Mock the sentiment analyzer pipeline
        mock_sentiment = [{"label": "POSITIVE", "score": 0.9}]
        self.hf_tools.sentiment_analyzer = MagicMock(return_value=mock_sentiment)
        
        # Test sentiment analysis
        result = self.hf_tools.analyze_sentiment(self.test_text)
        self.assertEqual(result["label"], "positive")
        self.assertEqual(result["score"], 0.9)
        
        # Verify the pipeline was called correctly
        self.hf_tools.sentiment_analyzer.assert_called_with(self.test_text)
    
    def test_error_handling(self):
        """Test error handling in tools"""
        # Test summarization error
        self.hf_tools.summarizer = MagicMock(side_effect=Exception("Test error"))
        with self.assertRaises(Exception):
            self.hf_tools.summarize_text(self.test_text)
        
        # Test classification error
        self.hf_tools.classifier = MagicMock(side_effect=Exception("Test error"))
        with self.assertRaises(Exception):
            self.hf_tools.classify_text(self.test_text)
        
        # Test sentiment analysis error
        self.hf_tools.sentiment_analyzer = MagicMock(side_effect=Exception("Test error"))
        with self.assertRaises(Exception):
            self.hf_tools.analyze_sentiment(self.test_text)

if __name__ == '__main__':
    unittest.main() 