import unittest
import os
import sys
import platform

# Add parent directory to path to import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import after path setup
import config

class TestConfig(unittest.TestCase):
    def test_platform_specific_config(self):
        """Test that platform-specific configuration is properly loaded."""
        system = platform.system()
        expected_config = config.PLATFORM_CONFIGS.get(system, config.PLATFORM_CONFIGS["Linux"])
        
        self.assertEqual(config.MODEL_NAME, expected_config["whisper_model"])
        self.assertEqual(config.OLLAMA_MODEL, expected_config["ollama_model"])
        
    def test_directory_paths(self):
        """Test that directory paths are correctly configured."""
        self.assertTrue(os.path.isabs(config.BASE_DIR))
        self.assertTrue(os.path.isabs(config.TRANSCRIPT_DIR))
        self.assertTrue(os.path.isabs(config.SUMMARY_DIR))
        
        # Check path relationships
        self.assertIn("data", config.TRANSCRIPT_DIR)
        self.assertIn("transcripts", config.TRANSCRIPT_DIR)
        self.assertIn("data", config.SUMMARY_DIR)
        self.assertIn("summaries", config.SUMMARY_DIR)

if __name__ == '__main__':
    unittest.main()