import unittest
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_helpers import create_test_summary_dir, cleanup_test_summaries

class JarvisTestCase(unittest.TestCase):
    """Base test case class for Jarvis tests"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a test directory for summaries
        self.test_summary_dir = create_test_summary_dir()
        
    def tearDown(self):
        """Clean up test environment"""
        # Clean up all test summaries
        cleanup_test_summaries(self.test_summary_dir)