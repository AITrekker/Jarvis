import unittest
from unittest.mock import patch, mock_open
import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.file_store import load_recent_transcripts, save_transcript
from config import TRANSCRIPT_AGGREGATION_MIN

class TestLoadTranscripts(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_load_recent_transcripts(self):
        """Test loading transcripts from a specific time."""
        # Create test transcripts
        now = datetime.utcnow()
        
        # Create transcripts at different times
        timestamps = [
            now - timedelta(minutes=30),  # 30 min ago
            now - timedelta(minutes=20),  # 20 min ago
            now - timedelta(minutes=10),  # 10 min ago
            now                           # now
        ]
        
        # Save test transcripts
        for i, ts in enumerate(timestamps):
            save_transcript(f"Test transcript {i+1}", ts.isoformat(), 
                           directory=self.test_dir, quiet=True)
        
        # Test loading from 15 minutes ago
        since_time = (now - timedelta(minutes=15)).isoformat()
        
        # Override TRANSCRIPT_DIR for testing
        import storage.file_store
        original_dir = storage.file_store.TRANSCRIPT_DIR
        storage.file_store.TRANSCRIPT_DIR = self.test_dir
        
        try:
            # Load recent transcripts
            results = load_recent_transcripts(since_time)
            
            # Should find 2 transcripts (10 min ago and now)
            self.assertEqual(len(results), 2)
            
            # Check timestamps are in order
            self.assertTrue(results[0]['timestamp'] < results[1]['timestamp'])
            
            # Check content
            self.assertIn("Test transcript", results[0]['transcript'])
        finally:
            # Restore original directory
            storage.file_store.TRANSCRIPT_DIR = original_dir
    
    def test_load_from_empty_directory(self):
        """Test loading from an empty directory."""
        # Override TRANSCRIPT_DIR for testing with empty dir
        import storage.file_store
        original_dir = storage.file_store.TRANSCRIPT_DIR
        storage.file_store.TRANSCRIPT_DIR = self.test_dir  # Empty temp dir
        
        try:
            # Load recent transcripts
            since_time = datetime.utcnow().isoformat()
            results = load_recent_transcripts(since_time)
            
            # Should be empty
            self.assertEqual(len(results), 0)
        finally:
            # Restore original directory
            storage.file_store.TRANSCRIPT_DIR = original_dir
    
    def test_load_with_invalid_files(self):
        """Test loading with invalid JSON files."""
        # Create an invalid JSON file
        now = datetime.utcnow()
        interval_timestamp = now.replace(minute=(now.minute // TRANSCRIPT_AGGREGATION_MIN) * TRANSCRIPT_AGGREGATION_MIN, 
                                         second=0, microsecond=0)
        filename = f"transcript_{interval_timestamp.isoformat().replace(':', '-')}.json"
        filepath = os.path.join(self.test_dir, filename)
        
        # Write invalid JSON
        with open(filepath, 'w') as f:
            f.write("This is not valid JSON")
        
        # Override TRANSCRIPT_DIR for testing
        import storage.file_store
        original_dir = storage.file_store.TRANSCRIPT_DIR
        storage.file_store.TRANSCRIPT_DIR = self.test_dir
        
        try:
            # Load recent transcripts
            since_time = (now - timedelta(minutes=5)).isoformat()
            results = load_recent_transcripts(since_time)
            
            # Should handle the error and return empty list
            self.assertEqual(len(results), 0)
        finally:
            # Restore original directory
            storage.file_store.TRANSCRIPT_DIR = original_dir

if __name__ == '__main__':
    unittest.main()