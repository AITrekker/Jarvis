"""
Chat Interface Component Module

This module provides the chat interface functionality for the Jarvis web application,
allowing users to interact with Jarvis through text-based conversations.

Role in the system:
- Manages chat history in the session state
- Handles user message input and processing
- Displays conversation history in a chat-like interface
- Connects chat input to the search and RAG functionality
- Provides UI elements for chat interaction (input box, message display)

Used by the main web UI to provide text-based interaction with Jarvis.
"""

import streamlit as st
from web.web_utils.search_handler import search_conversations

def render_chat_page():
    """Render the Chat page."""
    st.header("💬 Chat with Jarvis")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Add input field with callback
    st.text_input(
        "Ask Jarvis a question...",
        key="chat_input",
        on_change=handle_chat_input,
        placeholder="Type your question and press Enter..."
    )

def handle_chat_input():
    """Handle user input from the chat interface."""
    prompt = st.session_state.chat_input
    if prompt:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response from search
        with st.chat_message("assistant"):
            with st.spinner("Searching conversations..."):
                # Search with RAG enhancement
                search_result = search_conversations(prompt, top_k=5)
                
                if search_result and "rag_response" in search_result:
                    # Display the RAG-enhanced response
                    st.markdown(search_result["rag_response"])
                    
                    # Add "View Source Results" expander
                    with st.expander("View Source Results"):
                        for i, result in enumerate(search_result["raw_results"], 1):
                            date = result["metadata"]["timestamp"].split("T")[0]
                            summary = result["metadata"]["summary"]
                            
                            # Calculate relevance from either distance or similarity
                            if "distance" in result:
                                relevance = 100 * (1 - result["distance"]) 
                            elif "similarity" in result:
                                relevance = 100 * result["similarity"]
                            else:
                                relevance = 50  # Default value if neither exists
                                
                            st.markdown(f"**Result {i} - {date} (Relevance: {relevance:.1f}%)**")
                            st.markdown(summary)
                            st.markdown("---")
                else:
                    st.markdown("I couldn't find any relevant information in your conversations.")
        
        # Add assistant response to chat history
        if search_result and "rag_response" in search_result:
            st.session_state.messages.append({"role": "assistant", "content": search_result["rag_response"]})
        else:
            st.session_state.messages.append({"role": "assistant", "content": "I couldn't find any relevant information in your conversations."})