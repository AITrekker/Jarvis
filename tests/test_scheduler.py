import unittest
import os
import sys

# Add parent directory to path to import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the base test case
from tests.test_base import JarvisTestCase

# Import the scheduler module to inspect what schedule implementation it's using
from utils.periodic_tasks import start_scheduler

# Look for the schedule module import within your periodic_tasks module
import inspect
import importlib

class TestScheduler(JarvisTestCase):
    def setUp(self):
        # Call the parent setUp
        super().setUp()
        
        # First, find out what scheduler module your code is actually using
        periodic_tasks_module = sys.modules.get('scheduler.periodic_tasks')
        
        # Try to find the schedule module used
        self.schedule = None
        for name, module in sys.modules.items():
            if name.endswith('schedule') and hasattr(module, 'jobs'):
                self.schedule = module
                break
                
        # If still not found, try a different approach
        if not self.schedule:
            # Look for common scheduler implementations
            try:
                self.schedule = importlib.import_module('schedule')
            except ImportError:
                pass
                
        if not self.schedule:
            self.skipTest("Could not find schedule module")
            return
            
        # Save original jobs
        self.original_jobs = self.schedule.jobs.copy()
        self.schedule.clear()
        
    def tearDown(self):
        if hasattr(self, 'schedule') and self.schedule:
            # Clear test jobs
            self.schedule.clear()
            # Restore original jobs
            for job in self.original_jobs:
                self.schedule.jobs.append(job)
        
        # Call the parent tearDown to clean up test summaries
        super().tearDown()
            
    def test_basic_scheduler_operation(self):
        """Test that we can interact with the scheduler."""
        if not hasattr(self, 'schedule') or not self.schedule:
            self.skipTest("Scheduler module not available")
            
        self.assertTrue(hasattr(self.schedule, 'jobs'))
        self.assertTrue(hasattr(self.schedule, 'clear'))
        
    def test_scheduler_starts(self):
        """Test that the start_scheduler function runs."""
        # This just verifies that start_scheduler runs without error
        thread = start_scheduler()
        self.assertIsNotNone(thread)

if __name__ == '__main__':
    unittest.main()