import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web.web_utils.search_handler import search_conversations, highlight_keywords

class TestSearchHandler(unittest.TestCase):
    
    # Update these patch paths to use web.web_utils instead of web.utils
    @patch('web.web_utils.search_handler.generate_embedding')
    @patch('web.web_utils.search_handler.unified_search')
    def test_search_conversations(self, mock_unified_search, mock_gen_embedding):
        # Setup
        mock_gen_embedding.return_value = [0.1, 0.2, 0.3]
        mock_unified_search.return_value = {
            "success": True, 
            "rag_response": "Test response"
        }
        
        # Update this path as well
        with patch('web.web_utils.search_handler.st.session_state', 
                   MagicMock(ollama_model="test-model")):
            result = search_conversations("test query")
        
        # Assert
        mock_gen_embedding.assert_called_once_with("test query")
        mock_unified_search.assert_called_once()
        self.assertEqual(result["rag_response"], "Test response")
    
    def test_highlight_keywords(self):
        # Test the keyword highlighting functionality
        text = "This is a test sentence with keywords."
        keywords = ["test", "keywords"]
        result = highlight_keywords(text, keywords)
        
        expected = "This is a <span class='highlight'>test</span> sentence with <span class='highlight'>keywords</span>."
        self.assertEqual(result, expected)