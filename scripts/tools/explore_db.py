import os
from pymongo import MongoClient
from pprint import pprint
from collections import defaultdict
import json
from datetime import datetime
from bson import ObjectId

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, ObjectId)):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

def get_field_types(doc, prefix=''):
    """Recursively determine field types in a document"""
    schema = {}
    for key, value in doc.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            schema.update(get_field_types(value, full_key))
        else:
            schema[full_key] = type(value).__name__
    return schema

def analyze_collection(collection, collection_name):
    """Analyze a collection's structure"""
    output = []
    output.append(f"\n--- Collection: {collection_name} ---\n")
    
    # Get total documents
    total_docs = collection.count_documents({})
    output.append(f"Total Documents: {total_docs}\n")
    
    if total_docs > 0:
        # Get schema from first document
        first_doc = collection.find_one()
        schema = get_field_types(first_doc)
        output.append("\nSchema:")
        for field, field_type in schema.items():
            output.append(f"  {field}: {field_type}")
        
        # Get indexes
        indexes = collection.list_indexes()
        output.append("\nIndexes:")
        for idx in indexes:
            output.append(f"  {idx['name']}: {idx['key']}")
        
        # Get sample documents
        output.append("\nSample Documents:")
        for doc in collection.find().limit(2):
            output.append(json.dumps(doc, indent=2, cls=JSONEncoder))
    
    output.append("\n" + "-" * 50)
    return "\n".join(output)

def main():
    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGO_DB_URL', 'mongodb://localhost:27017'))
    
    with open('db_structure.txt', 'w') as f:
        f.write("\n=== MongoDB Database Structure ===\n")
        
        # Check ghostwriter database
        f.write("\nDatabase: ghostwriter\n")
        db = client['ghostwriter']
        collections = ['raw_content', 'processed_content', 'url_tracking']
        for coll_name in collections:
            f.write(analyze_collection(db[coll_name], coll_name))
        
        # Check content_data database
        f.write("\nDatabase: content_data\n")
        db = client['content_data']
        collections = ['raw_content', 'processed_content']
        for coll_name in collections:
            f.write(analyze_collection(db[coll_name], coll_name))
        
        # Check search database (from MONGODB_DB_NAME1)
        db_name = os.getenv('MONGODB_DB_NAME1', 'search_data')
        f.write(f"\nDatabase: {db_name}\n")
        db = client[db_name]
        collections = ['searches']
        for coll_name in collections:
            f.write(analyze_collection(db[coll_name], coll_name))

if __name__ == "__main__":
    main() 