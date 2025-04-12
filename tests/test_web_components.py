import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the streamlit module
sys.modules['streamlit'] = MagicMock()
import streamlit as st

# Import components after mocking
from web.components.sidebar import render_sidebar
from web.components.chat import render_chat_page, handle_chat_input

class TestSidebar(unittest.TestCase):
    """Tests for the sidebar component."""
    
    @patch('streamlit.sidebar')
    def test_render_sidebar(self, mock_sidebar):
        """Test that sidebar renders correctly."""
        # We need to patch the entire streamlit module and the recorder controls
        with patch('web.components.sidebar.st') as mock_st, \
             patch('web.components.sidebar.render_recorder_controls') as mock_controls:
            
            # Setup mock columns
            mock_cols = [MagicMock(), MagicMock(), MagicMock()]
            mock_st.sidebar.columns.return_value = mock_cols
            mock_st.session_state = {}
            
            # Import here to avoid import errors
            from web.components.sidebar import render_sidebar
            
            # Call the function
            result = render_sidebar()
            
            # Check that sidebar was rendered
            mock_st.sidebar.title.assert_called_once()
            mock_controls.assert_called_once()

    @patch('streamlit.columns')
    def test_render_recorder_controls(self, mock_columns):
        """Test that recorder controls render correctly."""
        # Need to patch all the st function calls
        with patch('web.components.recorder_controls.st') as mock_st, \
             patch('web.components.recorder_controls.start_transcription') as mock_start, \
             patch('web.components.recorder_controls.pause_transcription') as mock_pause, \
             patch('web.components.recorder_controls.resume_transcription') as mock_resume, \
             patch('web.components.recorder_controls.stop_transcription') as mock_stop:
            
            # Setup mock columns
            mock_cols = [MagicMock(), MagicMock(), MagicMock()]
            mock_st.sidebar.columns.return_value = mock_cols
            mock_st.session_state = {
                "is_recording": False,
                "is_paused": False,
                "console_output": ["Test output"]
            }
            
            # Setup button click behavior
            mock_cols[0].button.return_value = True  # Start button clicked
            mock_cols[1].button.return_value = False
            mock_cols[2].button.return_value = False
            
            # Import and test
            from web.components.recorder_controls import render_recorder_controls
            
            # Call the function
            render_recorder_controls()
            
            # Check that start was called
            mock_start.assert_called_once()
            mock_pause.assert_not_called()
            mock_stop.assert_not_called()

class TestChatComponent(unittest.TestCase):
    
    @patch('web.components.chat.st.session_state', 
           MagicMock(messages=[], chat_input="How does Jarvis work?"))
    @patch('web.components.chat.search_conversations')
    def test_handle_chat_input(self, mock_search):
        """Test the chat input handler."""
        # Setup
        mock_search.return_value = {
            "success": True,
            "rag_response": "Jarvis works by processing audio and using RAG.",
            "raw_results": [
                {"metadata": {"timestamp": "2023-04-01T12:00", "summary": "Example"}, 
                 "distance": 0.2}
            ]
        }
        
        # Execute
        with patch('web.components.chat.st.chat_message') as mock_chat_message:
            with patch('web.components.chat.st.markdown'):
                with patch('web.components.chat.st.spinner'):
                    with patch('web.components.chat.st.expander'):
                        handle_chat_input()
        
        # Assert
        mock_search.assert_called_once()
        self.assertEqual(len(st.session_state.messages), 2)  # User + assistant messages
        self.assertEqual(st.session_state.messages[0]["role"], "user")
        self.assertEqual(st.session_state.messages[1]["role"], "assistant")

if __name__ == '__main__':
    unittest.main()