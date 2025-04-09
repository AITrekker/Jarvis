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

from utils.summarize import create_summary_prompt, save_summary, generate_with_ollama, summarize_recent_transcripts
from config import (
    SUMMARY_INTERVAL_MIN, SUMMARY_MAX_CHARS, 
    SUMMARY_FILE_ROLLOVER_MIN 
)

class TestSummarizer(unittest.TestCase):
    
    @patch('logging.getLogger')
    def setUp(self, mock_logger):
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        # Mock logger to prevent errors in tests
        self.mock_logger = MagicMock()
        mock_logger.return_value = self.mock_logger
        
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
    
    def test_create_summary_prompt_with_speakers(self):
        """Test creating a prompt from transcript data with speaker segments."""
        transcripts = [
            {
                "timestamp": "2025-04-05T04:22:00",
                "transcript": "Speaker 1: Hello there. Speaker 2: Hi, how are you?",
                "segments": [
                    {"speaker": "Speaker 1", "text": "Hello there."},
                    {"speaker": "Speaker 2", "text": "Hi, how are you?"}
                ]
            }
        ]
        
        prompt = create_summary_prompt(transcripts)
        
        # Check that prompt contains speaker labels
        self.assertIn("Speaker 1:", prompt)
        self.assertIn("Hello there.", prompt)
        self.assertIn("Speaker 2:", prompt)
        self.assertIn("Hi, how are you?", prompt)
        
        # Check that the prompt mentions conversation (not just transcribed speech)
        self.assertIn("conversation", prompt.lower())

    @patch('utils.summarize.USE_SUMMARY_CHUNKING', True)
    def test_create_summary_prompt_chunking(self):
        """Test that long transcripts are properly split into chunks when chunking is enabled."""
        long_text = " ".join(["word"] * 20000)  # Very long transcript
        transcripts = [{"timestamp": "2025-04-05T04:22:00", "transcript": long_text}]
        
        prompt = create_summary_prompt(transcripts)
        
        # Check that the prompt includes all chunks (no data loss)
        self.assertIn("[Transcript chunked due to length.]", prompt)
        self.assertGreaterEqual(len(prompt), SUMMARY_MAX_CHARS)  # Ensure prompt is at least one chunk long
        self.assertEqual(prompt.count("word"), 20000)  # Ensure all words are included

    @patch('utils.summarize.USE_SUMMARY_CHUNKING', False)
    def test_create_summary_prompt_no_chunking(self):
        """Test that long transcripts are not chunked when chunking is disabled."""
        long_text = " ".join(["word"] * 10000)  # Create a very long transcript
        transcripts = [{"timestamp": "2025-04-05T04:22:00", "transcript": long_text}]
        
        prompt = create_summary_prompt(transcripts)
        
        # Check that the full text is included (not truncated)
        self.assertGreaterEqual(len(prompt), len(long_text))
        self.assertNotIn("[Transcript truncated", prompt)  # Verify no truncation message

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
    
    @patch('utils.summarize.logger')
    @patch('requests.post')
    def test_generate_with_ollama_error(self, mock_post, mock_logger):
        """Test error handling in Ollama API call."""
        # Mock error
        mock_post.side_effect = requests.exceptions.RequestException("API error")
        
        # Call function
        result = generate_with_ollama("Test prompt")
        
        # Check error handling
        self.assertIn("Error generating summary", result)
    
    @patch('utils.summarize.generate_embedding')
    def test_save_summary(self, mock_generate_embedding):
        """Test saving a summary to a file."""
        # Mock embedding function to return simple vector
        mock_generate_embedding.return_value = [0.1, 0.2, 0.3]

        # Create test data
        summary_text = "This is a test summary."
        source_transcripts = [
            {"timestamp": "2025-04-05T04:22:00", "transcript": "This is the first transcript."},
            {"timestamp": "2025-04-05T04:24:00", "transcript": "This is the second transcript."}
        ]
        
        # Override summary directory for testing
        with patch('utils.summarize.SUMMARY_DIR', self.test_dir):
            # Mock datetime.utcnow to return a fixed time for consistent testing
            with patch('utils.summarize.datetime') as mock_datetime:
                # Set to 2025-04-05 10:30:00
                mock_now = datetime(2025, 4, 5, 10, 30, 0)
                mock_datetime.utcnow.return_value = mock_now
                
                # Save summary
                filepath = save_summary(summary_text, source_transcripts)
                
                # Check that file exists
                self.assertTrue(os.path.exists(filepath))
                
                # Verify the filename format (should be hourly)
                expected_filename = f"summary_2025-04-05T10-00-00.json"
                self.assertTrue(filepath.endswith(expected_filename))
                
                # Load and check file content
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    
                    # Check structure (should have entries array)
                    self.assertIn('entries', data)
                    self.assertEqual(len(data['entries']), 1)
                    
                    # Check content of first entry
                    entry = data['entries'][0]
                    self.assertEqual(entry['summary'], summary_text)
                    self.assertEqual(entry['source_count'], 2)
                    self.assertEqual(entry['period_minutes'], SUMMARY_INTERVAL_MIN)
    
    def test_save_summary_rollover_interval(self):
        """Test that summaries roll over correctly based on SUMMARY_FILE_ROLLOVER_MIN."""
        summary_text = "Test summary."
        source_transcripts = [{"timestamp": "2025-04-05T04:22:00", "transcript": "Test transcript."}]

        with patch('utils.summarize.SUMMARY_DIR', self.test_dir):
            with patch('utils.summarize.datetime') as mock_datetime:
                # Create a mock datetime object
                mock_now = datetime(2025, 4, 5, 10, 45, 0)
                # Set it as the return value for utcnow()
                mock_datetime.utcnow.return_value = mock_now

                filepath = save_summary(summary_text, source_transcripts)

                # With SUMMARY_FILE_ROLLOVER_MIN = 60, this should create a file for 10:00
                expected_filename = f"summary_2025-04-05T10-00-00.json"
                self.assertTrue(filepath.endswith(expected_filename))
    
    @patch('utils.summarize.generate_embedding')
    def test_save_summary_with_embedding(self, mock_generate_embedding):
        """Test saving summary with embedding."""
        mock_generate_embedding.return_value = [0.1, 0.2, 0.3]  # Mock embedding

        summary_text = "Test summary."
        source_transcripts = [{"timestamp": "2025-04-05T04:22:00", "transcript": "Test transcript."}]

        with patch('utils.summarize.SUMMARY_DIR', self.test_dir):
            filepath = save_summary(summary_text, source_transcripts)

            with open(filepath, 'r') as f:
                data = json.load(f)
                entry = data['entries'][-1]
                self.assertIn('embedding', entry)
                self.assertEqual(entry['embedding'], [0.1, 0.2, 0.3])
    
    @patch('utils.summarize.load_recent_transcripts')
    @patch('utils.summarize.generate_with_ollama')
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
        with patch('utils.summarize.SUMMARY_DIR', self.test_dir):
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
    
    @patch('utils.summarize.load_recent_transcripts')
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