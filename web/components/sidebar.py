"""
Sidebar Component Module

This module provides the sidebar functionality for the Jarvis web application,
organizing navigation, controls, and information in the side panel.

Role in the system:
- Displays application information and branding
- Contains recorder controls for audio capture
- Provides access to settings and configuration
- Shows system status information
- Houses auxiliary controls and information panels

Used by the main web UI to provide consistent sidebar navigation and controls.
"""

import streamlit as st
from web.components.recorder_controls import render_recorder_controls

def render_sidebar():
    """Render the sidebar with controls."""
    st.sidebar.title("Jarvis")
    st.sidebar.markdown("---")
    
    # Render recorder controls
    render_recorder_controls()
    
    #st.sidebar.markdown("---")
    #st.sidebar.markdown("### Settings")
    
    # Other settings can remain here
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info("""
    **Jarvis** is your personal AI assistant.
    
    It helps you keep track of your conversations 
    and provides insights from your audio.
    """)