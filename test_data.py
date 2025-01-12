from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017')
db = client['ghostwriter']

# Test document
test_doc = {
    'url': 'https://example.com/test1',
    'title': 'Test Article 1',
    'date_crawled': datetime.now().isoformat(),
    'processing_status': 'raw',
    'source': 'web',
    'text': 'This is a test article content.',
    'metadata': {'author': 'Test Author'},
    'content_hash': 'test_hash_123'
}

# Insert the document
result = db.raw_content.insert_one(test_doc)
print(f"Inserted document with ID: {result.inserted_id}")

# Verify the document was inserted
doc = db.raw_content.find_one({'url': 'https://example.com/test1'})
print(f"Retrieved document: {doc}") 