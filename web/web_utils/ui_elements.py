"""
UI Elements Utility Module

This module provides common UI elements and styling helpers used across
the Jarvis web application components.

Role in the system:
- Provides consistent styling for UI components
- Loads CSS for custom appearance and animations
- Contains reusable UI elements and component templates
- Handles custom formatting and display logic
- Ensures visual consistency throughout the application

Used by various web components to maintain a consistent look and feel
across the entire Jarvis web interface.
"""

import streamlit as st

def load_css():
    """Load custom CSS for the app."""
    # Add your original CSS here without the sticky tabs modifications
    st.markdown("""
    <style>
        .chat-message {
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            display: flex;
            flex-direction: column;
        }
        .chat-message.user {
            background-color: #e6f3ff;
            border-left: 5px solid #2e86de;
        }
        .chat-message.assistant {
            background-color: #f5f5f5;
            border-left: 5px solid #8e44ad;
        }
        .chat-message .message-content {
            margin-top: 0.5rem;
        }
        .highlight {
            background-color: #ffffcc;
            padding: 0.2rem;
            border-radius: 0.2rem;
        }
        .source-link {
            font-size: 0.8rem;
            color: #666;
            text-decoration: none;
        }
        .timeline-card {
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        /* Recording status styling */
        [data-testid=stSidebar] h4 {
            margin-top: 0;
            margin-bottom: 1rem;
        }
        [data-testid=stSidebar] h4:contains("Recording") {
            color: #ff4b4b;
            font-weight: bold;
        }
        [data-testid=stSidebar] h4:contains("Paused") {
            color: #ff9d00;
            font-weight: bold;
        }
        [data-testid=stSidebar] h4:contains("Stopped") {
            color: #31c950;
            font-weight: bold;
        }
        
        /* Console output styling */
        .stCodeBlock {
            max-height: 500px; /* Increased from 300px */
            overflow-y: auto;
            font-size: 0.9rem; /* Slightly larger font */
        }
        
        /* Expand console area in sidebar */
        [data-testid=stSidebar] .stCodeBlock {
            width: 100%;
            max-height: 400px; /* Bigger console in sidebar */
        }
        
        /* Button styling */
        .stButton button:first-child {
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        /* Make button colors more consistent with their function */
        div[data-testid="column"]:nth-child(1) button:enabled:hover {
            background-color: rgba(0, 128, 0, 0.1) !important;
            color: green !important;
        }
        
        div[data-testid="column"]:nth-child(2) button:enabled:hover {
            background-color: rgba(255, 165, 0, 0.1) !important;
            color: #ff9900 !important;
        }
        
        div[data-testid="column"]:nth-child(3) button:enabled:hover {
            background-color: rgba(255, 0, 0, 0.1) !important;
            color: red !important;
        }
        
        /* Navigation tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-left: 20px;
            padding-right: 20px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #e6f3ff;
            border-bottom: 2px solid #1e88e5;
            font-weight: bold;
        }
        
        /* Add some spacing between tabs and content */
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 16px;
        }

        /* Dark mode support */
        .stTabs {
            background-color: var(--background-color);
        }
        
        /* Dark mode support for tabs */
        [data-theme="dark"] .stTabs [data-baseweb="tab-list"] {
            background-color: var(--background-color);
        }
    </style>
    """, unsafe_allow_html=True)