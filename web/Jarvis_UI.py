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
    
    # Render sidebar
    render_sidebar()
    
    # Create and render tabs
    tabs = st.tabs(["💬 Chat", "🔍 Topic Explorer", "📅 Conversation Timeline"])
    
    with tabs[0]:
        render_chat_page()
    
    with tabs[1]:
        render_topic_explorer()
        
    with tabs[2]:
        render_timeline_tab()

if __name__ == "__main__":
    main()