import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
import sys

# Add parent directory to path to import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.db import save_transcript
from config import SUMMARY_INTERVAL_MIN

class TestDB(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        
        # Store original interval and override for testing
        self.original_interval = SUMMARY_INTERVAL_MIN
        import config
        config.SUMMARY_INTERVAL_MIN = 15  # Ensure consistent test behavior

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
        # Restore original interval
        import config
        config.SUMMARY_INTERVAL_MIN = self.original_interval

    def test_save_transcript_creates_file(self):
        """Test that save_transcript creates a file when none exists."""
        timestamp = datetime.utcnow().isoformat()
        save_transcript("Test transcript", timestamp, directory=self.test_dir, quiet=True)
        
        # Check directory contents
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 1, "Should create exactly one file")

    def test_save_transcript_aggregates_by_interval(self):
        """Test that transcripts from the same interval are aggregated."""
        # Create a timestamp
        now = datetime.utcnow()
        # Make sure timestamps are in the same 15-min interval
        base_time = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        timestamp1 = (base_time + timedelta(minutes=5)).isoformat()
        timestamp2 = (base_time + timedelta(minutes=10)).isoformat()
        
        # Save two transcripts within the same interval
        save_transcript("First transcript", timestamp1, directory=self.test_dir, quiet=True)
        save_transcript("Second transcript", timestamp2, directory=self.test_dir, quiet=True)
        
        # There should still be only one file
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 1, f"Should still have only one file for the same {SUMMARY_INTERVAL_MIN}-minute interval")
        
        # Check file content - should have two entries
        with open(os.path.join(self.test_dir, files[0]), 'r') as f:
            data = json.load(f)
            self.assertIn('entries', data, "File should have 'entries' key")
            self.assertEqual(len(data['entries']), 2, "Should have two entries")

    def test_save_transcript_different_intervals(self):
        """Test that transcripts from different intervals go to different files."""
        # Create timestamps in different intervals
        now = datetime.utcnow()
        base_time = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        timestamp1 = base_time.isoformat()
        timestamp2 = (base_time + timedelta(minutes=15)).isoformat()  # Next interval
        
        save_transcript("First interval", timestamp1, directory=self.test_dir, quiet=True)
        save_transcript("Second interval", timestamp2, directory=self.test_dir, quiet=True)
        
        # Should have two files
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 2, f"Should create two files for different {SUMMARY_INTERVAL_MIN}-minute intervals")

    def test_save_transcript_appends_to_existing(self):
        """Test that save_transcript appends to existing file."""
        # Create a timestamp
        now = datetime.utcnow()
        base_time = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        timestamp = (base_time + timedelta(minutes=5)).isoformat()
        
        # Save first transcript
        save_transcript("First transcript", timestamp, directory=self.test_dir, quiet=True)
        
        # Get the created file
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 1, "Should create exactly one file")
        filepath = os.path.join(self.test_dir, files[0])
        
        # Read the file to get initial state
        with open(filepath, 'r') as f:
            initial_data = json.load(f)
            initial_entries = len(initial_data['entries'])
        
        # Save another transcript with same interval
        save_transcript("Second transcript", timestamp, directory=self.test_dir, quiet=True)
        
        # Read the file again
        with open(filepath, 'r') as f:
            updated_data = json.load(f)
            updated_entries = len(updated_data['entries'])
        
        # Should have one more entry
        self.assertEqual(updated_entries, initial_entries + 1, 
                        "Should have added exactly one more entry")

    def test_handles_corrupt_json(self):
        """Test that save_transcript handles corrupt JSON files."""
        timestamp = datetime.utcnow().isoformat()
        timestamp_obj = datetime.fromisoformat(timestamp)
        rounded_minute = (timestamp_obj.minute // 15) * 15
        interval_timestamp = timestamp_obj.replace(minute=rounded_minute, second=0, microsecond=0)
        filename = f"transcript_{interval_timestamp.isoformat().replace(':', '-')}.json"
        filepath = os.path.join(self.test_dir, filename)
        
        # Create a corrupt JSON file
        os.makedirs(self.test_dir, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write("This is not valid JSON")
        
        # Try to save a transcript - should handle the corrupt file
        save_transcript("Test transcript", timestamp, directory=self.test_dir, quiet=True)
        
        # Now the file should be valid JSON
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.assertIn('entries', data, "File should have 'entries' key")