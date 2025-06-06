"""
Search Handler Module

This module provides the logic for handling search queries from the web interface,
coordinating with the search subsystem to retrieve and process results.

Role in the system:
- Receives search queries from the web UI
- Calls the appropriate search functions from the search subsystem
- Formats search results for display in the UI
- Handles different search modes (e.g., semantic, keyword)
- Integrates with the RAG model for enhanced responses

Used by the chat component to provide contextually relevant information
from past conversations to the language model.
"""

import logging
from search.search_engine import unified_search
from web.web_utils.session import session_state
from search.ollama_helper import get_embedding
from storage.chroma_store import get_all_summaries as get_all_conversations
from storage.chroma_store import delete_summary_by_id as delete_conversation

logger = logging.getLogger(__name__)

def search_conversations(query, top_k=5, model=None):
    """
    Performs a unified search for conversations, using embeddings and optional RAG.
    """
    if not query:
        return None
    
    model_to_use = model if model else session_state.ollama_model
    if not model_to_use:
        logger.warning("No Ollama model specified or found in session state for search.")
        return {"success": False, "message": "No model selected"}
        
    embedding = get_embedding(query, model=model_to_use)
    if not embedding:
        return {"success": False, "message": "Failed to get embedding for query"}

    try:
        result = unified_search(query, embedding, top_k, use_rag=True, model=model_to_use)
        return result
    except Exception as e:
        logger.error(f"Error during RAG search: {e}")
        return None

# By importing and aliasing from chroma_store, we no longer need the incorrect,
# locally defined get_all_conversations and delete_conversation functions.
# The timeline component will now call the correct backend functions directly. 