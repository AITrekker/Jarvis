import streamlit as st
import os
import sys

# Disable telemetry for Streamlit
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_TELEMETRY'] = 'false'

# Add project root to path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import config
from config import (
    UI_PAGE_TITLE, UI_PAGE_ICON, UI_LAYOUT, UI_SIDEBAR_STATE
)

# Import storage
from storage.chroma_store import initialize_chroma

# Import components and utilities
from components.sidebar import render_sidebar
from components.chat import render_chat_page
from components.topic_explorer import render_topic_explorer
from components.timeline import render_timeline
# Update these imports
from web_utils.ui_elements import load_css
from web_utils.session import initialize_session_state

def main():
    """Main entry point for the Jarvis UI Pro application."""
    # Initialize ChromaDB
    initialize_chroma(force=True)
    
    # Page configuration - use config values
    st.set_page_config(
        page_title=UI_PAGE_TITLE,
        page_icon=UI_PAGE_ICON,
        layout=UI_LAYOUT,
        initial_sidebar_state=UI_SIDEBAR_STATE
    )
    
    # Load custom CSS
    load_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Render selected page
    if page == "Chat":
        render_chat_page()
    elif page == "Topic Explorer":
        render_topic_explorer()
    elif page == "Conversation Timeline":
        render_timeline()

if __name__ == "__main__":
    main()