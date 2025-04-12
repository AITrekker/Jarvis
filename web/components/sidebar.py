import streamlit as st
from web.components.recorder_controls import render_recorder_controls

def render_sidebar():
    """Render the sidebar with controls."""
    st.sidebar.title("Jarvis")
    st.sidebar.markdown("---")
    
    # Render recorder controls
    render_recorder_controls()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Settings")
    
    # Other settings can remain here
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info("""
    **Jarvis** is your personal AI assistant.
    
    It helps you keep track of your conversations 
    and provides insights from your audio.
    """)