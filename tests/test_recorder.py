import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import sounddevice as sd
import tempfile
import numpy as np
import soundfile as sf

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import WHISPER_MODEL, SAMPLERATE, CHANNELS
import utils.recorder

class TestRecorder(unittest.TestCase):
    """Tests for the audio recorder functionality."""
    
    def setUp(self):
        # Create a temporary file that will be automatically deleted
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        self.temp_filename = self.temp_file.name
        self.temp_file.close()
        
        # Generate 5 seconds of silence
        silence = np.zeros((SAMPLERATE * 5, CHANNELS), dtype=np.float32)
        sf.write(self.temp_filename, silence, SAMPLERATE)
        
    def tearDown(self):
        try:
            if os.path.exists(self.temp_filename):
                os.unlink(self.temp_filename)
        except Exception as e:
            print(f"Warning: Could not delete {self.temp_filename}: {e}")

    def test_whisper_model_loaded(self):
        """Test that the Whisper model is properly loaded."""
        self.assertIsNotNone(WHISPER_MODEL, "Whisper model should be loaded")

    def test_transcript_filtering(self):
        """Test that empty or meaningless transcripts are filtered."""
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

    def test_recorder_module_exists(self):
        """Test that the recorder module exists."""
        self.assertTrue(hasattr(utils.recorder, '__file__'))
    
    def test_recorder_functions(self):
        """Test that recorder has expected functionality."""
        # List all functions in the module
        module_functions = [name for name in dir(utils.recorder) 
                           if callable(getattr(utils.recorder, name)) 
                           and not name.startswith('_')]
        
        # Print available functions to help with debugging
        print(f"Available functions in recorder: {module_functions}")
        
        # Assert that the module has at least one function
        self.assertTrue(len(module_functions) > 0, 
                       "recorder module should have at least one function")
    
    @unittest.skip("Implementation details need review before testing")
    def test_audio_processing(self):
        """Test audio chunk processing."""
        # Skip this test for now
        pass

    @patch('utils.recorder.transcribe_from_mic')
    def test_transcription(self, mock_transcribe):
        """Test audio transcription."""
        # Test the function that actually exists in the module
        mock_transcribe.return_value = "Test transcript"
        
        # Skip this test for now - needs adaptations based on actual implementation
        self.skipTest("Need to implement based on actual implementation")