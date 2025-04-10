import streamlit as st
from utils.summarize import generate_embedding  
from search.search_engine import unified_search
from config import SEARCH_DEFAULT_TOP_K

def search_conversations(query, top_k=SEARCH_DEFAULT_TOP_K):
    """Search conversations using the query with RAG."""
    try:
        # Generate embedding for the query
        embedding = generate_embedding(query)
        
        # Use unified search function
        return unified_search(
            query=query, 
            embedding=embedding, 
            top_k=top_k, 
            use_rag=True,
            model=st.session_state.ollama_model
        )
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return []
        
def highlight_keywords(text, keywords):
    """Highlight keywords in text."""
    highlighted = text
    for keyword in keywords:
        if len(keyword) > 3:  # Only highlight keywords longer than 3 chars
            highlighted = highlighted.replace(keyword, f"<span class='highlight'>{keyword}</span>")
    return highlighted