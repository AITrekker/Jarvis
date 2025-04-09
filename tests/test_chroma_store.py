import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import pytest

# First mock the is_test_mode flag and logger to control test behavior
with patch('search.chroma_store.is_test_mode', False), \
     patch('search.chroma_store.logger', MagicMock()):
    # Then import the module
    from search.chroma_store import add_summary_embedding, search_summaries, get_all_summaries

# A simpler approach with a test fixture
@pytest.fixture
def chroma_store():
    with patch('search.chroma_store.is_test_mode', False), \
         patch('search.chroma_store.summaries_collection', MagicMock()):
        from search.chroma_store import add_summary_embedding
        yield add_summary_embedding

class TestChromaStore(unittest.TestCase):
    
    def setUp(self):
        """Set up mock collections for each test."""
        patcher = patch('search.chroma_store.summaries_collection')
        self.mock_collection = patcher.start()
        self.addCleanup(patcher.stop)
        
        # Ensure is_test_mode is False during tests so the real code path is tested
        patcher2 = patch('search.chroma_store.is_test_mode', False)
        patcher2.start()
        self.addCleanup(patcher2.stop)
    
    def test_add_summary_embedding(self):
        """Test adding a summary embedding to ChromaDB"""
        # Setup
        self.mock_collection.add.return_value = None
        embedding = [0.1, 0.2, 0.3]
        summary_text = "Test summary"
        source_transcripts = [{"timestamp": "2025-04-08T10:00:00", "transcript": "Test transcript"}]
        timestamp = "2025-04-08T10:00:00"
        
        # Execute
        result = add_summary_embedding(embedding, summary_text, source_transcripts, timestamp)
        
        # Assert
        self.assertIsNotNone(result)
        self.mock_collection.add.assert_called_once()
        
        # Verify call arguments
        call_args = self.mock_collection.add.call_args[1]
        self.assertEqual(call_args['embeddings'], [embedding])
        
        # Check metadata
        metadata = call_args['metadatas'][0]
        self.assertEqual(metadata['summary'], summary_text)
        self.assertEqual(metadata['timestamp'], timestamp)
        self.assertEqual(metadata['source_count'], 1)
        self.assertEqual(metadata['first_transcript_time'], source_transcripts[0]['timestamp'])
        
    @patch('search.chroma_store.summaries_collection')
    def test_search_summaries(self, mock_collection):
        """Test searching summaries in ChromaDB"""
        # Setup
        mock_results = {
            "ids": [["id1", "id2"]],
            "metadatas": [[
                {"summary": "Test summary 1", "timestamp": "2025-04-08T10:00:00"},
                {"summary": "Test summary 2", "timestamp": "2025-04-08T10:01:00"}
            ]],
            "documents": [[
                "[{\"timestamp\": \"2025-04-08T10:00:00\", \"transcript\": \"Test transcript 1\"}]",
                "[{\"timestamp\": \"2025-04-08T10:01:00\", \"transcript\": \"Test transcript 2\"}]"
            ]],
            "distances": [[0.1, 0.2]]
        }
        mock_collection.query.return_value = mock_results
        query_embedding = [0.1, 0.2, 0.3]
        
        # Execute
        results = search_summaries(query_embedding, top_k=2)
        
        # Assert
        self.assertEqual(len(results), 2)
        mock_collection.query.assert_called_once_with(
            query_embeddings=[query_embedding],
            n_results=2
        )
        
        # Verify results were processed correctly
        self.assertEqual(results[0]['id'], "id1")
        self.assertEqual(results[0]['metadata']['summary'], "Test summary 1")
        self.assertEqual(results[0]['distance'], 0.1)
        self.assertEqual(results[1]['id'], "id2")
        self.assertEqual(results[1]['metadata']['summary'], "Test summary 2")
        self.assertEqual(results[1]['distance'], 0.2)

    @patch('search.chroma_store.summaries_collection')
    def test_get_all_summaries(self, mock_collection):
        """Test getting all summaries from ChromaDB"""
        # Setup
        mock_results = {
            "ids": ["id1", "id2"],
            "metadatas": [
                {"summary": "Test summary 1", "timestamp": "2025-04-08T10:00:00"},
                {"summary": "Test summary 2", "timestamp": "2025-04-08T10:01:00"}
            ],
            "documents": [
                "[{\"timestamp\": \"2025-04-08T10:00:00\", \"transcript\": \"Test transcript 1\"}]",
                "[{\"timestamp\": \"2025-04-08T10:01:00\", \"transcript\": \"Test transcript 2\"}]"
            ]
        }
        mock_collection.get.return_value = mock_results
        
        # Execute
        results = get_all_summaries(limit=10)
        
        # Assert
        self.assertEqual(len(results), 2)
        mock_collection.get.assert_called_once_with(limit=10)
        
        # Verify results were processed correctly
        self.assertEqual(results[0]['id'], "id1")
        self.assertEqual(results[0]['metadata']['summary'], "Test summary 1")
        self.assertEqual(results[1]['id'], "id2")
        self.assertEqual(results[1]['metadata']['summary'], "Test summary 2")

if __name__ == '__main__':
    unittest.main()