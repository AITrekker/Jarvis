"""
Chat Interface Component Module

This module provides the chat interface functionality for the Jarvis web application,
allowing users to interact with Jarvis through text-based conversations.
"""

import streamlit as st
from web.web_utils.search_handler import search_conversations

def render_chat_page():
    """Render the Chat page."""
    st.header("💬 Chat with Jarvis")
    
    # Add input field with callback at the top so it doesn't move
    st.text_input(
        "Ask Jarvis a question...",
        key="chat_input",
        on_change=handle_chat_input,
        placeholder="Type your question and press Enter..."
    )
    
    # Display chat history in reverse order (newest messages first)
    for message in reversed(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # If this is an assistant message with sources, show them in an expander
            if message["role"] == "assistant" and "sources" in message:
                with st.expander("View Source Results"):
                    for i, source in enumerate(message["sources"], 1):
                        st.markdown(f"**Result {i} - {source['date']} (Relevance: {source['relevance']:.1f}%)**")
                        st.markdown(source["summary"])
                        st.markdown("---")

# Keep your handle_chat_input function unchanged
def handle_chat_input():
    """Handle user input from the chat interface."""
    prompt = st.session_state.chat_input
    if prompt:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Search with RAG enhancement
        search_result = search_conversations(prompt, top_k=5)
        
        # Create assistant response
        if search_result and "rag_response" in search_result:
            response = search_result["rag_response"]
            
            # Store source results with the message for display in the UI
            sources = []
            for result in search_result["raw_results"]:
                date = result["metadata"]["timestamp"].split("T")[0]
                summary = result["metadata"]["summary"]
                
                # Calculate relevance
                if "distance" in result:
                    relevance = 100 * (1 - result["distance"]) 
                elif "similarity" in result:
                    relevance = 100 * result["similarity"]
                else:
                    relevance = 50  # Default value if neither exists
                
                sources.append({
                    "date": date, 
                    "summary": summary, 
                    "relevance": relevance
                })
            
            # Add assistant response to chat history with sources
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "sources": sources
            })
        else:
            response = "I couldn't find any relevant information in your conversations."
            st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Clear the input field after submission
        st.session_state.chat_input = ""