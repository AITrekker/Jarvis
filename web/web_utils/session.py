"""
Session State Management Module

This module handles the initialization and management of session state variables
used throughout the Jarvis web application.

Role in the system:
- Initializes session state variables on application startup
- Provides default values for settings and configuration
- Ensures consistent session state across different components
- Manages persistence of user preferences and history
- Centralizes session state management to avoid duplication

Used by the main web UI during initialization and by components that need
access to persistent state variables.
"""

class SessionState:
    def __init__(self):
        self._state = {}

    def __getattr__(self, name):
        return self._state.get(name)

    def __setattr__(self, name, value):
        if name == "_state":
            super().__setattr__(name, value)
        else:
            self._state[name] = value

# Global session state
session_state = SessionState()

def initialize_session_state():
    """Initialize session state variables."""
    if session_state.messages is None:
        session_state.messages = []
        
    if session_state.search_results is None:
        session_state.search_results = []
        
    if session_state.selected_topic is None:
        session_state.selected_topic = None
        
    # Recording state
    if session_state.is_recording is None:
        session_state.is_recording = False
    
    if session_state.is_paused is None:
        session_state.is_paused = False
        
    if session_state.recorder_process is None:
        session_state.recorder_process = None
        
    if session_state.console_output is None:
        session_state.console_output = []
        
    # Model selection
    if session_state.ollama_model is None:
        from config import UI_DEFAULT_MODEL
        session_state.ollama_model = UI_DEFAULT_MODEL

    # Add any tab-specific initialization if needed
    if session_state.chat_messages is None:
        session_state.chat_messages = []
        
    if session_state.topic_results is None:
        session_state.topic_results = []

def get_recording_state():
    """Get the current recording state."""
    return session_state.is_recording and not session_state.is_paused

def set_recording_state(state):
    """Set the recording state."""
    if state:
        session_state.is_recording = True
        session_state.is_paused = False
    else:
        session_state.is_paused = True 