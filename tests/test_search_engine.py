import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the correct functions based on your actual implementation
from search.search_engine import unified_search
from storage.chroma_store import search_summaries

class TestSearchEngine(unittest.TestCase):
    """Tests for the search engine module."""
    
    @patch('search.search_engine.search_summaries')
    @patch('search.search_engine.rag_search')
    def test_unified_search(self, mock_rag, mock_search):
        """Test the unified_search function with RAG."""
        # Setup
        mock_search.return_value = [{"document": "doc1", "metadata": {"summary": "test"}, "distance": 0.5}]
        mock_rag.return_value = "Enhanced results with RAG"
        
        # Execute
        result = unified_search(
            query="test query",
            embedding=[0.1, 0.2, 0.3],
            top_k=3,
            use_rag=True,
            model="test-model"
        )
        
        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["rag_response"], "Enhanced results with RAG")
        mock_search.assert_called_once_with([0.1, 0.2, 0.3], top_k=3)
        mock_rag.assert_called_once()
    
    def test_unified_search_no_results(self):
        """Test unified_search with no results."""
        # Mock the search_summaries and search_by_keywords functions
        with patch("search.search_engine.search_summaries") as mock_search_summaries, \
             patch("search.search_engine.search_by_keywords") as mock_search_keywords:
            # Set up mocks to return empty results
            mock_search_summaries.return_value = []
            mock_search_keywords.return_value = []
            
            # Call the function
            result = unified_search("test query", [0.1, 0.2, 0.3])
            
            # Actual current behavior has success=False
            self.assertFalse(result["success"])
            self.assertEqual(result.get("message"), "No results found")
            self.assertEqual(len(result.get("raw_results", [])), 0)