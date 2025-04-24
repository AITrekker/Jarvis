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
    """Render the sidebar with controls and navigation."""
    st.sidebar.title("Jarvis")
    st.sidebar.markdown("---")
    
    # Create navigation tabs in the sidebar
    selected_tab = st.sidebar.radio(
        "Navigation",
        ["Chat", "Topic Explorer", "Conversation Timeline"],
        key="sidebar_navigation",
        format_func=lambda x: f"💬 {x}" if x == "Chat" else 
                             f"🔍 {x}" if x == "Topic Explorer" else
                             f"📅 {x}" if x == "Conversation Timeline" else x
    )
    
    # Render recorder controls below navigation
    st.sidebar.markdown("---")
    render_recorder_controls()
    
    return selected_tab

    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info("""
    **Jarvis** is your personal AI assistant.
    
    It helps you keep track of your conversations 
    and provides insights from your audio.
    """)