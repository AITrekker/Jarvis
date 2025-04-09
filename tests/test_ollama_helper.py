import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from search.ollama_helper import query_ollama, rag_search

class TestOllamaHelper(unittest.TestCase):
    """Tests for the Ollama Helper module."""
    
    @patch('search.ollama_helper.requests.post')
    def test_query_ollama_success(self, mock_post):
        """Test successful Ollama API call."""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is a test response"}
        mock_post.return_value = mock_response
        
        # Execute
        response = query_ollama("System prompt", "User prompt", model="test-model")
        
        # Assert
        self.assertEqual(response, "This is a test response")
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]["json"]
        self.assertEqual(call_args["model"], "test-model")
        self.assertIn("System prompt", call_args["prompt"])
        self.assertIn("User prompt", call_args["prompt"])
    
    @patch('search.ollama_helper.requests.post')
    def test_query_ollama_api_error(self, mock_post):
        """Test handling of API errors."""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        # Execute
        response = query_ollama("System prompt", "User prompt")
        
        # Assert
        self.assertIn("Error querying Ollama", response)
        self.assertIn("500", response)
    
    @patch('search.ollama_helper.requests.post')
    def test_query_ollama_exception(self, mock_post):
        """Test handling of exceptions."""
        # Setup
        mock_post.side_effect = Exception("Network error")
        
        # Execute
        response = query_ollama("System prompt", "User prompt")
        
        # Assert
        self.assertIn("Error", response)
        self.assertIn("Network error", response)
    
    @patch('search.ollama_helper.query_ollama')
    def test_rag_search(self, mock_query):
        """Test RAG search functionality."""
        # Setup
        mock_query.return_value = "Processed results for your query"
        search_results = [
            {
                "metadata": {
                    "timestamp": "2025-04-05T10:00:00",
                    "summary": "Test summary 1"
                },
                "distance": 0.2
            },
            {
                "metadata": {
                    "timestamp": "2025-04-06T15:30:00",
                    "summary": "Test summary 2"
                },
                "distance": 0.4
            }
        ]
        
        # Execute
        result = rag_search("test query", search_results)
        
        # Assert
        self.assertEqual(result, "Processed results for your query")
        
        # Verify that query_ollama was called
        mock_query.assert_called_once()
    
    @patch('search.ollama_helper.query_ollama')
    def test_rag_search_empty_results(self, mock_query):
        """Test RAG search with empty results."""
        # Setup
        mock_query.return_value = "I couldn't find any relevant information."
        
        # Execute
        result = rag_search("test query", [])
        
        # Assert
        self.assertEqual(result, "I couldn't find any relevant information.")
        mock_query.assert_called_once()