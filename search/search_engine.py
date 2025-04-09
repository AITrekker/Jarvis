import sys
import os
from typing import List, Dict, Any, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.chroma_store import search_summaries
from search.ollama_helper import rag_search
from setup.logger import logger

def unified_search(query: str, 
                   embedding: List[float], 
                   top_k: int = 5, 
                   use_rag: bool = True,
                   model: str = "phi3") -> Dict[str, Any]:
    """
    Unified search function that combines vector search with optional RAG.
    
    Args:
        query: The user's text query
        embedding: The query embedding vector
        top_k: Number of results to return
        use_rag: Whether to use RAG to enhance results
        model: Which model to use for RAG
        
    Returns:
        Dictionary containing search results and RAG response if applicable
    """
    try:
        # Perform vector search
        results = search_summaries(embedding, top_k=top_k)
        
        if not results or len(results) == 0:
            return {"success": False, "message": "No results found", "raw_results": []}
            
        if use_rag:
            # Use RAG to enhance results if requested
            try:
                rag_response = rag_search(query, results, model=model)
                return {
                    "success": True,
                    "raw_results": results,
                    "rag_response": rag_response
                }
            except Exception as e:
                logger.error(f"Error in RAG processing: {str(e)}")
                # Fall back to raw results if RAG fails
                return {
                    "success": True,
                    "raw_results": results,
                    "error": f"RAG processing failed: {str(e)}"
                }
        else:
            # Return raw results without RAG
            return {
                "success": True,
                "raw_results": results
            }
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return {"success": False, "message": f"Search error: {str(e)}", "raw_results": []}