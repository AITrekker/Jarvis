import streamlit as st

def load_css():
    """Load custom CSS styling."""
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
    </style>
    """, unsafe_allow_html=True)