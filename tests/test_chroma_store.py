import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.chroma_store import add_summary_embedding, search_summaries, get_all_summaries

class TestChromaStore(unittest.TestCase):
    
    def setUp(self):
        # Mock the get_collections function instead of trying to access summaries_collection directly
        # This function is called inside the summaries_db module functions
        patcher = patch('storage.chroma.summaries_db.get_collections')
        self.mock_get_collections = patcher.start()
        
        # Create a mock collection
        self.mock_collection = MagicMock()
        
        # Configure the mock to return our mock collection as the first item in the tuple
        # The get_collections function returns (summaries_collection, transcripts_collection)
        self.mock_get_collections.return_value = (self.mock_collection, MagicMock())
        
        self.addCleanup(patcher.stop)
        
    def test_add_summary_embedding(self):
        """Test adding a summary embedding to ChromaDB."""
        # Test data - use realistic dimensions (768) to avoid dimension mismatch
        embedding = [0.1] * 768  # 768-dimensional vector
        summary_text = "Test summary"
        source_transcripts = [{"id": "123", "timestamp": "2025-04-22T12:00:00"}]
        
        # Call function with proper datetime mocking
        with patch('datetime.datetime') as mock_datetime:
            # Use a string instead of a MagicMock for the timestamp
            mock_datetime.now.return_value.isoformat.return_value = "2025-04-22T12:00:00"
            add_summary_embedding(embedding, summary_text, source_transcripts)
        
        # Verify collection was called with correct parameters
        self.mock_collection.add.assert_called_once()
        
    def test_search_summaries(self):
        """Test searching summaries in ChromaDB."""
        # Mock return value
        self.mock_collection.query.return_value = {
            "distances": [[0.1]],
            "documents": [["Test summary"]],
            "metadatas": [[{"timestamp": "2025-04-05T12:00:00"}]],
            "ids": [["123"]]
        }
        
        # Test data - use realistic dimensions (768)
        query_embedding = [0.1] * 768
        
        # Call function
        results = search_summaries(query_embedding)
        
        # Verify collection was called correctly
        self.mock_collection.query.assert_called_once()
        
        # Check that we got results
        self.assertEqual(len(results), 1)
        
    def test_get_all_summaries(self):
        """Test getting all summaries from ChromaDB."""
        # Mock return value - using valid JSON string in documents field
        # The key issue is that the JSON string format needs to be correct for json.loads()
        self.mock_collection.get.return_value = {
            "embeddings": [[0.1, 0.2, 0.3]],
            # Fix: Use a proper JSON string, not a list representation
            "documents": ['{"id":"123","timestamp":"2025-04-05T12:00:00"}'],
            "metadatas": [{"timestamp": "2025-04-05T12:00:00"}],
            "ids": ["123"]
        }
        
        # Call function
        results = get_all_summaries()
        
        # Verify collection was called correctly
        self.mock_collection.get.assert_called_once()
        
        # Check that we got results
        self.assertEqual(len(results), 1)

if __name__ == '__main__':
    unittest.main()