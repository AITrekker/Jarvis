import streamlit as st

def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
        
    if "selected_topic" not in st.session_state:
        st.session_state.selected_topic = None