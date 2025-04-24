"""
Web User Interface Module

This module provides the user interface for the Jarvis web application,
based on Streamlit, enabling users to interact with Jarvis through the browser.

Role in the system:
- Creates and manages the main UI for Jarvis
- Sets up navigation between different tabs/pages
- Initializes session state for web interactions
- Handles user input and displays responses
- Integrates all web components into a unified interface

This is the main entry point for the web-based interface, handling page
routing and component initialization.
"""

import streamlit as st
import os
import sys
import atexit

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import config - environment variables are set when this is imported
from config import (
    UI_PAGE_TITLE, UI_PAGE_ICON, UI_LAYOUT, UI_SIDEBAR_STATE
)

# Import storage
from storage.chroma_store import initialize_chroma
from setup.setup import check_dependencies
from setup.logger import logger
from components.sidebar import render_sidebar
from components.chat import render_chat_page
from components.topic_explorer import render_topic_explorer
from components.timeline import render_timeline
from web_utils.ui_elements import load_css
from web_utils.session import initialize_session_state
from components.recorder_controls import stop_recording

# Register cleanup function
atexit.register(lambda: stop_recording() if st.session_state.get("is_recording", False) else None)

def setup_page():
    """Initialize page settings and core components"""
    # Initialize ChromaDB
    initialize_chroma(force=True)
    
    # Configure page
    st.set_page_config(
        page_title=UI_PAGE_TITLE,
        page_icon=UI_PAGE_ICON,
        layout=UI_LAYOUT,
        initial_sidebar_state=UI_SIDEBAR_STATE
    )
    
    # Load CSS and initialize state
    load_css()
    initialize_session_state()

def render_timeline_tab():
    """Render timeline tab with refresh button"""
    # Add refresh button for timeline data
    col1, col2 = st.columns([0.85, 0.15])
    with col2:
        if st.button("🔄 Refresh", key="refresh_timeline"):
            with st.spinner("Refreshing data..."):
                initialize_chroma(force=True)
                st.toast("Timeline data refreshed successfully!")
    
    render_timeline()

def main():
    """Main entry point for the Jarvis UI application"""
    # Show warning if not launched from main.py
    if not os.environ.get("JARVIS_INITIALIZED"):
        st.warning("⚠️ For best experience, launch Jarvis using: `python main.py --mode ui`")
        try:
            check_dependencies()
        except Exception as e:
            st.error(f"Dependency check failed: {str(e)}")
            logger.error(f"Dependency check failed: {str(e)}")
    
    # Setup the page
    setup_page()
    
    # Render sidebar and get selected tab
    selected_tab = render_sidebar()
    
    # Render the appropriate component based on sidebar selection
    if selected_tab == "Chat":
        render_chat_page()
    elif selected_tab == "Topic Explorer":
        render_topic_explorer()
    elif selected_tab == "Conversation Timeline":
        render_timeline_tab()
    else:
        # Default to chat
        render_chat_page()

if __name__ == "__main__":
    main()