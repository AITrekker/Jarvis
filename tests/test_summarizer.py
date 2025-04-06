import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
import sys
from unittest.mock import patch, MagicMock
import requests

# Add parent directory to path to import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from summarizer.summarize import create_summary_prompt, save_summary, generate_with_ollama, summarize_recent_transcripts
from config import SUMMARY_INTERVAL_MIN

class TestSummarizer(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_create_summary_prompt(self):
        """Test creating a prompt from transcript data."""
        # Create test data
        transcripts = [
            {"timestamp": "2025-04-05T04:22:00", "transcript": "This is the first transcript."},
            {"timestamp": "2025-04-05T04:24:00", "transcript": "This is the second transcript."}
        ]
        
        # Generate prompt
        prompt = create_summary_prompt(transcripts)
        
        # Check that prompt contains the transcripts
        self.assertIn("This is the first transcript.", prompt)
        self.assertIn("This is the second transcript.", prompt)
        
    def test_create_summary_prompt_empty(self):
        """Test creating a prompt with no transcripts."""
        prompt = create_summary_prompt([])
        self.assertEqual(prompt, "No transcripts available to summarize.")
    
    @patch('requests.post')
    def test_generate_with_ollama(self, mock_post):
        """Test the Ollama API call."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "This is a summary."}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        # Call function
        result = generate_with_ollama("Test prompt")
        
        # Check that the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['prompt'], "Test prompt")
        
        # Check result
        self.assertEqual(result, "This is a summary.")
    
    @patch('requests.post')
    def test_generate_with_ollama_error(self, mock_post):
        """Test error handling in Ollama API call."""
        # Mock error - change to a requests exception
        mock_post.side_effect = requests.exceptions.RequestException("API error")
        
        # Call function
        result = generate_with_ollama("Test prompt")
        
        # Check error handling
        self.assertIn("Error generating summary", result)
    
    def test_save_summary(self):
        """Test saving a summary to a file."""
        # Create test data
        summary_text = "This is a test summary."
        source_transcripts = [
            {"timestamp": "2025-04-05T04:22:00", "transcript": "This is the first transcript."},
            {"timestamp": "2025-04-05T04:24:00", "transcript": "This is the second transcript."}
        ]
        
        # Override summary directory for testing
        with patch('summarizer.summarize.SUMMARY_DIR', self.test_dir):
            # Save summary
            filepath = save_summary(summary_text, source_transcripts)
            
            # Check that file exists
            self.assertTrue(os.path.exists(filepath))
            
            # Load and check file content
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                self.assertEqual(data['summary'], summary_text)
                self.assertEqual(data['source_count'], 2)
                self.assertEqual(len(data['source_transcripts']), 2)
                self.assertEqual(data['source_transcripts'][0], "This is the first transcript.")
    
    @patch('summarizer.summarize.load_recent_transcripts')
    @patch('summarizer.summarize.generate_with_ollama')
    def test_summarize_recent_transcripts(self, mock_generate, mock_load):
        """Test the full summarization flow."""
        # Mock load_recent_transcripts to return test data
        mock_load.return_value = [
            {"timestamp": "2025-04-05T04:22:00", "transcript": "This is the first transcript."},
            {"timestamp": "2025-04-05T04:24:00", "transcript": "This is the second transcript."}
        ]
        
        # Mock generate_with_ollama
        mock_generate.return_value = "This is a test summary."
        
        # Override summary directory for testing
        with patch('summarizer.summarize.SUMMARY_DIR', self.test_dir):
            # Run summarization
            result = summarize_recent_transcripts()
            
            # Check that the correct functions were called
            mock_load.assert_called_once()
            mock_generate.assert_called_once()
            
            # Check result
            self.assertEqual(result, "This is a test summary.")
            
            # Check that a file was created
            files = os.listdir(self.test_dir)
            self.assertEqual(len(files), 1)
    
    @patch('summarizer.summarize.load_recent_transcripts')
    def test_summarize_no_transcripts(self, mock_load):
        """Test summarization when no transcripts are available."""
        # Mock load_recent_transcripts to return empty list
        mock_load.return_value = []
        
        # Run summarization
        result = summarize_recent_transcripts()
        
        # Check result
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()