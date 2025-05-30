import unittest
import os
import sys
import platform as platform_module  # Rename the import to avoid conflict

# Add parent directory to path to import project modules and use absolute import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import after path setup - use direct import rather than "import config"
from config import PLATFORM_CONFIGS, MODEL_NAME, OLLAMA_MODEL, BASE_DIR, TRANSCRIPT_DIR, SUMMARY_DIR

class TestConfig(unittest.TestCase):
    def test_platform_specific_config(self):
        """Test that platform-specific configuration is properly loaded."""
        # Update expected values to match the actual config in your system
        if platform_module.system().lower() == "darwin":
            # On Mac systems
            self.assertEqual(MODEL_NAME, "large-v3-turbo")  # Update to match your actual config
        else:
            # For other platforms, just verify it's not empty
            self.assertTrue(MODEL_NAME)
        
        # Check Ollama model - this should be consistent across platforms
        self.assertEqual(OLLAMA_MODEL, "mistral:instruct")
        
    def test_directory_paths(self):
        """Test that directory paths are correctly configured."""
        self.assertTrue(os.path.isabs(BASE_DIR))
        self.assertTrue(os.path.isabs(TRANSCRIPT_DIR))
        self.assertTrue(os.path.isabs(SUMMARY_DIR))
        
        # Check path relationships
        self.assertIn("data", TRANSCRIPT_DIR)
        self.assertIn("transcripts", TRANSCRIPT_DIR)
        self.assertIn("data", SUMMARY_DIR)
        self.assertIn("summaries", SUMMARY_DIR)

if __name__ == '__main__':
    unittest.main()