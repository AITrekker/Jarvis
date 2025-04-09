import unittest
from unittest.mock import patch
import sys
import os

# Import module to test
from search.search import search_transcripts

class TestSearch(unittest.TestCase):
    
    @patch('search.search.search_summaries')
    @patch('search.search.generate_embedding')
    def test_search_transcripts(self, mock_generate_embedding, mock_search_summaries):
        """Test searching for transcripts."""
        # Setup
        mock_generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_search_summaries.return_value = [
            {
                'id': 'id1',
                'metadata': {'summary': 'Test summary 1'},
                'source_transcripts': [{'transcript': 'Test transcript 1'}],
                'distance': 0.1
            }
        ]
        
        # Execute
        query = "test query"
        results = search_transcripts(query, top_k=3)
        
        # Assert
        mock_generate_embedding.assert_called_once_with(query)
        mock_search_summaries.assert_called_once_with([0.1, 0.2, 0.3], top_k=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], 'id1')
        self.assertEqual(results[0]['metadata']['summary'], 'Test summary 1')

    @patch('search.search.generate_embedding')
    def test_search_transcripts_handles_error(self, mock_generate_embedding):
        """Test search handles errors gracefully."""
        # Setup
        mock_generate_embedding.side_effect = Exception("Test error")
        
        # Execute
        results = search_transcripts("test query")
        
        # Assert
        self.assertEqual(results, [])

if __name__ == '__main__':
    unittest.main()