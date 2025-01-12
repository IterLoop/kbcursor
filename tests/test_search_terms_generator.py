import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC, timedelta
from scripts.api.search_terms_generator import SearchTermGenerator

@pytest.fixture
def search_term_generator():
    return SearchTermGenerator()

def test_validate_search_terms(search_term_generator):
    # Test valid terms
    terms = ["artificial intelligence in healthcare", "machine learning applications", "neural networks"]
    min_terms = 2
    max_terms = 5
    is_valid, message = search_term_generator.validate_search_terms(terms, min_terms, max_terms)
    assert is_valid
    assert "Generated" in message

    # Test too few terms
    is_valid, message = search_term_generator.validate_search_terms(terms, 5, 10)
    assert not is_valid
    assert "minimum required" in message

    # Test too many terms
    is_valid, message = search_term_generator.validate_search_terms(terms, 1, 2)
    assert not is_valid
    assert "exceeding maximum" in message

def test_clean_search_terms(search_term_generator):
    # Test basic cleaning
    text = "1. term1, 2. term2, 3. term3"
    terms = search_term_generator.clean_search_terms(text)
    assert all(isinstance(term, str) for term in terms)
    assert all(term.strip() == term for term in terms)
    assert len(terms) == 3

    # Test removing duplicates
    text = "term1, term1, TERM1, different term"
    terms = search_term_generator.clean_search_terms(text)
    assert len(terms) == 2

def test_get_term_count_range(search_term_generator):
    # Test base case (levels = 3)
    min_terms, max_terms = search_term_generator.get_term_count_range(3, 3)
    assert min_terms == 5
    assert max_terms == 10

    # Test high levels
    min_terms, max_terms = search_term_generator.get_term_count_range(5, 5)
    assert min_terms == 5 + 4  # base + max(imagination_bonus, research_bonus)
    assert max_terms == 10 + 8  # base + imagination_bonus + research_bonus

@patch("scripts.api.search_terms_generator.MongoDB")
def test_store_search_terms(mock_mongo, search_term_generator):
    # Create mock collection and properly set it up in the search_term_generator
    mock_collection = MagicMock()
    mock_mongo.return_value.db = MagicMock()
    mock_mongo.return_value.db.__getitem__.return_value = mock_collection
    search_term_generator.mongo = mock_mongo.return_value
    search_term_generator.article_requests = mock_collection  # Directly set the collection
    
    topic = "Test Topic"
    terms = ["term1", "term2"]
    params = {"param1": "value1"}
    
    # Test case 1: No existing article request
    mock_collection.find_one.return_value = None
    search_term_generator.store_search_terms(topic, terms, params)
    
    # Verify insert_one was called with correct data
    mock_collection.insert_one.assert_called_once()
    insert_call = mock_collection.insert_one.call_args[0][0]
    assert insert_call["outline"] == topic
    assert insert_call["status"] == "search_terms_generated"
    assert isinstance(insert_call["created_at"], datetime)
    
    # Test case 2: Existing article request
    mock_collection.reset_mock()
    existing_doc = {"_id": "abc123", "outline": topic}
    mock_collection.find_one.return_value = existing_doc
    
    search_term_generator.store_search_terms(topic, terms, params)
    
    # Verify update_one was called with correct data
    mock_collection.update_one.assert_called_once()
    filter_dict, update_dict = mock_collection.update_one.call_args[0]
    assert filter_dict == {"_id": "abc123"}
    assert "search_terms" in update_dict["$set"]
    assert "search_terms_generated_at" in update_dict["$set"]
    assert "search_parameters" in update_dict["$set"]
    assert update_dict["$set"]["status"] == "search_terms_generated" 