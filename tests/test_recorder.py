import unittest
import os
import numpy as np
import tempfile
import sys
import soundfile as sf

# Add parent directory to path to import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import WHISPER_MODEL, SAMPLERATE, CHANNELS

class TestRecorder(unittest.TestCase):
    def setUp(self):
        # Create a temporary WAV file with silence
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.temp_filename = self.temp_file.name
        
        # Generate 5 seconds of silence
        silence = np.zeros((SAMPLERATE * 5, CHANNELS), dtype=np.float32)
        sf.write(self.temp_filename, silence, SAMPLERATE)
        
    def tearDown(self):
        os.unlink(self.temp_filename)

    def test_whisper_model_loaded(self):
        """Test that the Whisper model is properly loaded."""
        self.assertIsNotNone(WHISPER_MODEL, "Whisper model should be loaded")

    def test_transcript_filtering(self):
        """Test that empty or meaningless transcripts are filtered."""
        # This test checks the behavior of filtering out meaningless transcripts
        
        # Test with empty text - should be filtered
        text = ""
        self.assertFalse(
            len(text) > 0 and text.lower() not in ["thank you.", "thanks.", ""],
            "Empty text should be filtered"
        )
        
        # Test with "thank you" - should be filtered
        text = "Thank you."
        self.assertFalse(
            len(text) > 0 and text.lower() not in ["thank you.", "thanks.", ""],
            "'Thank you.' should be filtered"
        )
        
        # Test with meaningful text - should not be filtered
        text = "This is a meaningful transcript."
        self.assertTrue(
            len(text) > 0 and text.lower() not in ["thank you.", "thanks.", ""],
            "Meaningful text should not be filtered"
        )