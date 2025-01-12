"""Vector database implementation using FAISS for efficient similarity search."""

import logging
import numpy as np
import faiss
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorDB:
    """Vector database for efficient similarity search."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize vector database.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        try:
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.index = faiss.IndexFlatL2(self.dimension)
            self.documents = []  # Store original documents
            logger.info(f"Successfully initialized VectorDB with model: {model_name}")
        except Exception as e:
            logger.error(f"Error initializing VectorDB: {str(e)}")
            raise
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            Numpy array containing the embedding
        """
        return self.model.encode([text])[0]
    
    def index_document(self, document: Dict[str, Any]) -> bool:
        """Index a document.
        
        Args:
            document: Dictionary containing document data with 'text' field
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if 'text' not in document:
                logger.error("Document missing 'text' field")
                return False
                
            embedding = self._get_embedding(document['text'])
            self.index.add(embedding.reshape(1, -1))
            self.documents.append(document)
            logger.info(f"Successfully indexed document: {document.get('id', len(self.documents)-1)}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing document: {str(e)}")
            return False
    
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of documents with similarity scores
        """
        try:
            query_embedding = self._get_embedding(query)
            scores, indices = self.index.search(query_embedding.reshape(1, -1), k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.documents):  # Ensure index is valid
                    doc = self.documents[idx].copy()
                    doc['score'] = float(score)  # Convert numpy float to Python float
                    results.append(doc)
                    
            logger.info(f"Found {len(results)} similar documents for query")
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
    
    def clear_test_data(self) -> None:
        """Clear all test data."""
        try:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.documents = []
            logger.info("Successfully cleared test data")
        except Exception as e:
            logger.error(f"Error clearing test data: {str(e)}")
    
    def get_document_count(self) -> int:
        """Get number of indexed documents.
        
        Returns:
            Number of documents in the index
        """
        return len(self.documents) 