"""
Utilities for search functionality in the web interface
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search.search_engine import normalize_search_results, unified_search
from setup.logger import logger

def format_search_results_for_display(search_results):
    """
    Format search results for display in the web interface.
    
    Args:
        search_results: Raw search results from unified_search
        
    Returns:
        List of formatted results ready for display
    """
    try:
        if not search_results.get("success", False):
            return []
            
        results = search_results.get("raw_results", [])
        formatted = []
        
        for result in results:
            # Ensure result has consistent structure
            normalized = result.copy()
            
            # Get content from the right place
            content = normalized.get("content", "")
            if not content and "metadata" in normalized and normalized["metadata"] and "summary" in normalized["metadata"]:
                content = normalized["metadata"]["summary"]
                
            # Get title from timestamp if available
            title = normalized.get("title", "")
            if not title and "metadata" in normalized and normalized["metadata"] and "timestamp" in normalized["metadata"]:
                title = normalized["metadata"]["timestamp"]
            elif not title:
                title = "No Title"
                
            # Format the result
            formatted_result = {
                "id": normalized.get("id", ""),
                "title": title,
                "content": content,
                "similarity": normalized.get("similarity", 0),
                "source": normalized.get("source", "unknown"),
                "date": normalized.get("metadata", {}).get("timestamp", "Unknown Date")
            }
            formatted.append(formatted_result)
            
        return formatted
        
    except Exception as e:
        logger.error(f"Error formatting search results: {str(e)}")
        return []

def perform_search(query, use_rag=True):
    """
    Perform search and handle all the necessary conversions.
    
    Args:
        query: User search query
        use_rag: Whether to use RAG for response generation
        
    Returns:
        Dictionary with formatted results and RAG response if applicable
    """
    try:
        # Note: In a real implementation, you'd generate an embedding here
        # For simplicity, we're using None to trigger keyword search
        search_results = unified_search(query, embedding=None, use_rag=use_rag)
        
        formatted_results = format_search_results_for_display(search_results)
        
        return {
            "success": search_results.get("success", False),
            "results": formatted_results,
            "rag_response": search_results.get("rag_response", ""),
            "message": search_results.get("message", "")
        }
        
    except Exception as e:
        logger.error(f"Search operation failed: {str(e)}")
        return {
            "success": False,
            "results": [],
            "message": f"Search failed: {str(e)}"
        }