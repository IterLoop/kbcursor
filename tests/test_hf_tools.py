import unittest
from unittest.mock import patch, MagicMock
from tools.hf_tools import HFTools

# Mock HF_CONFIG for testing
MOCK_HF_CONFIG = {
    'DEFAULT_MODELS': {
        'SUMMARIZER': 'test-summarizer',
        'CLASSIFIER': 'test-classifier',
        'SENTIMENT': 'test-sentiment'
    },
    'API_TOKENS': {
        'INFERENCE': 'test-token'
    },
    'MAX_LENGTH': 130,
    'MIN_LENGTH': 30
}

class TestHFTools(unittest.TestCase):
    """Test cases for HuggingFace Tools implementation"""
    
    @patch('tools.hf_tools.pipeline')
    @patch('tools.hf_tools.HF_CONFIG', MOCK_HF_CONFIG)
    def setUp(self, mock_pipeline):
        """Set up test fixtures"""
        self.mock_pipeline = mock_pipeline
        
        # Mock pipeline returns
        self.mock_summarizer = MagicMock()
        self.mock_classifier = MagicMock()
        self.mock_sentiment = MagicMock()
        
        def pipeline_side_effect(task, **kwargs):
            if task == 'summarization':
                return self.mock_summarizer
            elif task == 'zero-shot-classification':
                return self.mock_classifier
            elif task == 'sentiment-analysis':
                return self.mock_sentiment
            raise ValueError(f"Unknown task: {task}")
        
        self.mock_pipeline.side_effect = pipeline_side_effect
        
        self.hf_tools = HFTools()
        self.test_text = "This is a test text for processing. It contains multiple sentences and should be suitable for testing various NLP tasks."
    
    def test_init(self):
        """Test initialization of HFTools"""
        # Verify pipeline initialization
        self.assertEqual(self.mock_pipeline.call_count, 3)  # summarizer, classifier, sentiment
        
        # Verify pipeline calls with correct models and token
        pipeline_calls = self.mock_pipeline.call_args_list
        
        # Check summarization pipeline
        self.assertEqual(pipeline_calls[0][0][0], 'summarization')
        self.assertEqual(pipeline_calls[0][1]['model'], MOCK_HF_CONFIG['DEFAULT_MODELS']['SUMMARIZER'])
        self.assertEqual(pipeline_calls[0][1]['token'], MOCK_HF_CONFIG['API_TOKENS']['INFERENCE'])
        
        # Check classification pipeline
        self.assertEqual(pipeline_calls[1][0][0], 'zero-shot-classification')
        self.assertEqual(pipeline_calls[1][1]['model'], MOCK_HF_CONFIG['DEFAULT_MODELS']['CLASSIFIER'])
        self.assertEqual(pipeline_calls[1][1]['token'], MOCK_HF_CONFIG['API_TOKENS']['INFERENCE'])
        
        # Check sentiment pipeline
        self.assertEqual(pipeline_calls[2][0][0], 'sentiment-analysis')
        self.assertEqual(pipeline_calls[2][1]['model'], MOCK_HF_CONFIG['DEFAULT_MODELS']['SENTIMENT'])
        self.assertEqual(pipeline_calls[2][1]['token'], MOCK_HF_CONFIG['API_TOKENS']['INFERENCE'])
    
    def test_summarize_text(self):
        """Test text summarization"""
        # Mock the summarizer pipeline
        self.mock_summarizer.return_value = [{"summary_text": "Test summary"}]
        
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
        self.mock_summarizer.assert_called_with(
            self.test_text,
            max_length=100,
            min_length=30
        )
    
    def test_classify_text(self):
        """Test text classification"""
        # Mock the classifier pipeline
        self.mock_classifier.return_value = {
            "labels": ["test_label"],
            "scores": [0.95]
        }
        
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
        self.mock_classifier.assert_called_with(
            self.test_text,
            ["label1", "label2"]
        )
        
        # Test error handling
        self.mock_classifier.side_effect = Exception("Test error")
        result = self.hf_tools.classify_text(self.test_text)
        self.assertEqual(result, {"label": "error", "score": 0.0})
    
    def test_analyze_sentiment(self):
        """Test sentiment analysis"""
        # Mock the sentiment analyzer pipeline
        self.mock_sentiment.return_value = [{"label": "POSITIVE", "score": 0.9}]
        
        # Test sentiment analysis
        result = self.hf_tools.analyze_sentiment(self.test_text)
        self.assertEqual(result["label"], "positive")
        self.assertEqual(result["score"], 0.9)
        
        # Verify the pipeline was called correctly
        self.mock_sentiment.assert_called_with(self.test_text)
    
    def test_error_handling(self):
        """Test error handling in tools"""
        # Test summarization error
        self.mock_summarizer.side_effect = Exception("Test error")
        with self.assertRaises(Exception):
            self.hf_tools.summarize_text(self.test_text)
        
        # Test sentiment analysis error
        self.mock_sentiment.side_effect = Exception("Test error")
        with self.assertRaises(Exception):
            self.hf_tools.analyze_sentiment(self.test_text)
        
        # Test classification error (returns error object instead of raising)
        self.mock_classifier.side_effect = Exception("Test error")
        result = self.hf_tools.classify_text(self.test_text)
        self.assertEqual(result, {"label": "error", "score": 0.0})

if __name__ == '__main__':
    unittest.main() 