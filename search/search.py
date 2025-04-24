"""
Basic Search Functionality Module

This module provides the core search functionality for Jarvis, serving as a high-level
wrapper for vector search operations. It handles the conversion of text queries to
embeddings and performs vector searches through ChromaDB.

Role in the system:
- Primary entry point for simple vector searches
- Converts text queries to embeddings
- Performs vector searches using the chroma_store module
- Handles errors and provides appropriate logging

Used by higher-level search interfaces like search_engine.py and search_cli.py.
"""

from utils.summarize import generate_embedding
from storage.chroma_store import search_summaries
from setup.logger import logger

def search_transcripts(query, top_k=5):
    """
    Search for summaries similar to the query text.
    
    Args:
        query (str): The text to search for.
        top_k (int): Number of results to return.
        
    Returns:
        List[Dict]: List of dictionaries containing search results.
        
    Examples:
        >>> results = search_transcripts("meeting about project timeline")
        >>> print(f"Found {len(results)} relevant results")
    """
    logger.info(f"Searching for: {query}")
    
    try:
        # Generate embedding for the query text
        query_embedding = generate_embedding(query)
        
        # Search using the embedding - use named parameter here
        results = search_summaries(query_embedding, top_k=top_k)  # Fix is here
        
        logger.info(f"Found {len(results)} results for query: {query}")
        return results
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return []
