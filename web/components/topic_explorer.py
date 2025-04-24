"""
Topic Explorer Component Module

This module provides the topic exploration interface for the Jarvis web application,
allowing users to browse and search through past conversation summaries.

Role in the system:
- Displays searchable list of past conversation summaries
- Provides search functionality with semantic meaning
- Shows detailed view of selected conversations
- Enables filtering and sorting of conversation history
- Connects UI actions to vector search backend

Used by the main web UI to allow users to explore past conversations.
"""

import streamlit as st
from web.web_utils.search_handler import search_conversations

def render_topic_explorer():
    """Render the Topic Explorer page."""
    st.header("🔍 Explore Topics")
    
    # Add input field with callback
    st.text_input(
        "Enter a topic to explore",
        key="topic_query",
        on_change=handle_topic_search,
        placeholder="e.g., hot rod engine, Wild West party"
    )
    
    # Display results
    if st.session_state.search_results:
        st.subheader(f"Results for: {st.session_state.selected_topic}")
        
        # Display the RAG-enhanced summary first
        if "rag_response" in st.session_state.search_results:
            st.markdown("### AI Analysis")
            st.markdown(st.session_state.search_results["rag_response"])
            st.markdown("---")
            
            # Display source results
            st.markdown("### Source Conversations")
            for i, result in enumerate(st.session_state.search_results["raw_results"]):
                date = result["metadata"]["timestamp"].split("T")[0]
                summary = result["metadata"]["summary"]
                if "distance" in result:
                    relevance = 100 * (1 - result["distance"])
                elif "similarity" in result:
                    # If we have similarity (0-1 where 1 is best match), use it directly
                    relevance = 100 * result["similarity"]
                else:
                    # Default relevance if neither field exists
                    relevance = 50  # Default to 50% relevance
                with st.expander(f"Conversation on {date} (Relevance: {relevance:.1f}%)"):
                    st.markdown(f"**Summary:** {summary}")
                    st.markdown(f"**Source count:** {result['metadata']['source_count']} transcript entries")

def handle_topic_search():
    """Handle topic search input."""
    topic_query = st.session_state.topic_query
    if topic_query:
        with st.spinner("Searching for related topics..."):
            search_result = search_conversations(topic_query, top_k=5)
            st.session_state.search_results = search_result
            st.session_state.selected_topic = topic_query