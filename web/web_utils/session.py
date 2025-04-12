import streamlit as st

def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
        
    if "selected_topic" not in st.session_state:
        st.session_state.selected_topic = None
        
    # Recording state
    if "is_recording" not in st.session_state:
        st.session_state.is_recording = False
    
    if "is_paused" not in st.session_state:
        st.session_state.is_paused = False
        
    if "recorder_process" not in st.session_state:
        st.session_state.recorder_process = None
        
    if "console_output" not in st.session_state:
        st.session_state.console_output = []
        
    # Model selection
    if "ollama_model" not in st.session_state:
        from config import UI_DEFAULT_MODEL
        st.session_state.ollama_model = UI_DEFAULT_MODEL

    # Add any tab-specific initialization if needed
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        
    if "topic_results" not in st.session_state:
        st.session_state.topic_results = []

def get_recording_state():
    """Get the current recording state."""
    return st.session_state.is_recording and not st.session_state.is_paused

def set_recording_state(state):
    """Set the recording state."""
    if state:
        st.session_state.is_recording = True
        st.session_state.is_paused = False
    else:
        st.session_state.is_paused = True