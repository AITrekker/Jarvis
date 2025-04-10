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
    
    def test_render_sidebar(self):
        """Test that sidebar renders correctly and returns selected page."""
        # Setup
        st.sidebar.title = MagicMock()
        st.sidebar.selectbox = MagicMock(return_value="phi4")
        st.sidebar.radio = MagicMock(return_value="Chat")
        
        # Execute
        result = render_sidebar()
        
        # Assert
        st.sidebar.title.assert_called_once_with("🤖 Jarvis Assistant Pro")
        st.sidebar.selectbox.assert_called_once()
        st.sidebar.radio.assert_called_once()
        self.assertEqual(result, "Chat")

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