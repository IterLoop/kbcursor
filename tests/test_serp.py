import os
import sys
from pathlib import Path

# Add the project root directory to Python path
root_dir = str(Path(__file__).parent.parent)  # Go up one level to reach project root
sys.path.append(root_dir)

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from scripts.serp import connect_to_mongodb, save_to_mongodb, fetch_search_results

# Mock data for tests
MOCK_SEARCH_RESULTS = [
    {
        "url": "https://example.com",
        "meta_tags": {
            "title": "Example Title",
            "description": "Example Description"
        }
    }
]

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Setup environment variables for tests"""
    monkeypatch.setenv('MONGO_DB_URL', 'your_mongo_db_url')
    monkeypatch.setenv('MONGODB_DB_NAME1', 'test_db')
    monkeypatch.setenv('APIFY_API_KEY', 'test_api_key')

@pytest.fixture
def mock_mongo_client():
    """Setup mock MongoDB client"""
    with patch('scripts.serp.MongoClient') as mock_client:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        yield mock_client

def test_connect_to_mongodb_success(mock_env_vars, mock_mongo_client):
    """Test successful MongoDB connection"""
    db = connect_to_mongodb()
    assert db is not None
    mock_mongo_client.assert_called_once_with('your_mongo_db_url')

def test_connect_to_mongodb_missing_url(monkeypatch):
    """Test MongoDB connection with missing URL"""
    monkeypatch.delenv('MONGO_DB_URL', raising=False)
    with pytest.raises(ValueError, match="MONGO_DB_URL environment variable is not set"):
        connect_to_mongodb()

def test_connect_to_mongodb_missing_db_name(monkeypatch):
    """Test MongoDB connection with missing database name"""
    monkeypatch.setenv('MONGO_DB_URL', 'your_mongo_db_url')
    monkeypatch.delenv('MONGODB_DB_NAME1', raising=False)
    with pytest.raises(ValueError, match="MONGODB_DB_NAME1 environment variable is not set"):
        connect_to_mongodb()

def test_save_to_mongodb_success(mock_env_vars, mock_mongo_client):
    """Test successful save to MongoDB"""
    mock_collection = mock_mongo_client.return_value.__getitem__.return_value.__getitem__.return_value
    mock_collection.insert_one.return_value.inserted_id = 'test_id'

    save_to_mongodb(MOCK_SEARCH_RESULTS, "test search")
    
    # Verify the collection was called with correct data
    call_args = mock_collection.insert_one.call_args[0][0]
    assert call_args['search_term'] == "test search"
    assert call_args['results'] == MOCK_SEARCH_RESULTS
    assert isinstance(call_args['timestamp'], datetime)

@patch('scripts.serp.ApifyClient')
def test_fetch_search_results_success(mock_apify_client, mock_env_vars):
    """Test successful fetch of search results"""
    # Setup mock Apify response
    mock_run = MagicMock()
    mock_run.get.return_value = 'test_dataset_id'
    
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [{
        'organicResults': [{
            'url': 'https://example.com',
            'title': 'Example Title',
            'description': 'Example Description'
        }]
    }]
    
    mock_apify_client.return_value.actor.return_value.call.return_value = mock_run
    mock_apify_client.return_value.dataset.return_value = mock_dataset

    results = fetch_search_results("test search", 10)
    
    assert len(results) == 1
    assert results[0]['url'] == 'https://example.com'
    assert results[0]['meta_tags']['title'] == 'Example Title'
    assert results[0]['meta_tags']['description'] == 'Example Description'

def test_fetch_search_results_missing_api_key(monkeypatch):
    """Test fetch results with missing API key"""
    monkeypatch.delenv('APIFY_API_KEY', raising=False)
    with pytest.raises(ValueError, match="APIFY_API_KEY environment variable is not set"):
        fetch_search_results("test search", 10)

@patch('scripts.serp.ApifyClient')
def test_fetch_search_results_empty_response(mock_apify_client, mock_env_vars):
    """Test fetch results with empty response"""
    mock_run = MagicMock()
    mock_run.get.return_value = 'test_dataset_id'
    
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = []
    
    mock_apify_client.return_value.actor.return_value.call.return_value = mock_run
    mock_apify_client.return_value.dataset.return_value = mock_dataset

    results = fetch_search_results("test search", 10)
    assert len(results) == 0

@patch('scripts.serp.ApifyClient')
def test_fetch_search_results_invalid_response(mock_apify_client, mock_env_vars):
    """Test fetch results with invalid response format"""
    mock_run = MagicMock()
    mock_run.get.return_value = 'test_dataset_id'
    
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [
        None,  # Invalid item
        {'organicResults': None},  # Invalid organicResults
        {'organicResults': [None]},  # Invalid result
        {'organicResults': [{'url': None}]}  # Missing required fields
    ]
    
    mock_apify_client.return_value.actor.return_value.call.return_value = mock_run
    mock_apify_client.return_value.dataset.return_value = mock_dataset

    results = fetch_search_results("test search", 10)
    assert len(results) == 0 