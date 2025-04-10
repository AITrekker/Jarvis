import streamlit as st
from config import UI_DEFAULT_MODELS, UI_DEFAULT_MODEL

def render_sidebar():
    """Render the sidebar navigation and settings."""
    st.sidebar.title("🤖 Jarvis Assistant Pro")
    
    # Add model selection to sidebar
    available_models = UI_DEFAULT_MODELS
    selected_model = st.sidebar.selectbox(
        "Ollama Model", 
        available_models, 
        index=available_models.index(UI_DEFAULT_MODEL)
    )
    
    # Set the selected model in session state
    if "ollama_model" not in st.session_state:
        st.session_state.ollama_model = selected_model
    elif st.session_state.ollama_model != selected_model:
        st.session_state.ollama_model = selected_model
    
    # Navigation
    page = st.sidebar.radio("Navigation", ["Chat", "Topic Explorer", "Conversation Timeline"])
    
    return page