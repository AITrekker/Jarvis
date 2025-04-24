"""
Unified Search Engine Module

This module serves as the central search interface for Jarvis, combining 
vector-based search with RAG (Retrieval-Augmented Generation) capabilities.

Role in the system:
- Provides a unified search interface combining multiple search methods
- Integrates vector search with LLM-enhanced results
- Handles fallbacks and error cases gracefully
- Returns structured responses with both raw vector results and enhanced LLM responses

Primary entry point for advanced search operations in the web interface and API.
"""

import sys
import os
from typing import List, Dict, Any, Union
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.chroma_store import search_summaries
from search.ollama_helper import rag_search
from setup.logger import logger
# Import the correct model configuration
from config import OLLAMA_MODEL  # Use this existing configuration value

def normalize_search_results(results):
    """
    Normalize search results to have a consistent structure.
    
    Args:
        results: List of search results from various sources
        
    Returns:
        List of normalized results with consistent structure
    """
    normalized = []
    for result in results:
        normalized_result = result.copy()
        
        # Add content field at top level if it doesn't exist
        if not normalized_result.get("content") and "metadata" in normalized_result and "summary" in normalized_result["metadata"]:
            normalized_result["content"] = normalized_result["metadata"]["summary"]
        
        # Add title field at top level
        if not normalized_result.get("title"):
            normalized_result["title"] = normalized_result.get("metadata", {}).get("timestamp", "No Date")
        
        # Convert distance to similarity if present
        if "distance" in normalized_result and not "similarity" in normalized_result:
            # Distance is typically 0-1 where 0 is perfect match
            # Similarity should be 0-1 where 1 is perfect match
            normalized_result["similarity"] = 1.0 - float(normalized_result["distance"])
            
        # Ensure similarity exists (fallback if neither distance nor similarity exists)
        if "similarity" not in normalized_result:
            normalized_result["similarity"] = 0.5  # Default middle value
        
        normalized.append(normalized_result)
    return normalized

def search_by_keywords(query: str, summaries: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Perform a basic keyword search on summaries when vector search is insufficient.
    
    Args:
        query: The search query
        summaries: List of summaries to search through (if None, retrieves from storage)
        
    Returns:
        List of normalized matching results with added similarity score
    """
    from storage.chroma_store import get_all_summaries
    
    # Get summaries if not provided
    if summaries is None:
        summaries = get_all_summaries()
        logger.info(f"Retrieved {len(summaries)} summaries from ChromaDB")
    
    # Extract keywords (words longer than 2 chars to include more matches)
    keywords = [word.lower() for word in re.findall(r'\b\w+\b', query) if len(word) > 2]
    results = []
    
    # Add error checking for empty or invalid summaries
    if not summaries:
        logger.warning("No summaries retrieved from database")
        return []
    
    # Log the structure of the first summary to debug
    if summaries:
        logger.debug(f"Summary keys: {list(summaries[0].keys())}")
    
    for summary in summaries:
        # Add error checking for unexpected data structure
        if not isinstance(summary, dict):
            logger.warning(f"Unexpected summary type: {type(summary)}")
            continue
            
        # Get content from the correct location - check metadata.summary first
        content = ""
        if "metadata" in summary and summary["metadata"] and "summary" in summary["metadata"]:
            content = summary["metadata"]["summary"].lower()
        elif "content" in summary and summary["content"]:
            content = summary["content"].lower()
            
        # Skip if no content found
        if not content:
            continue
            
        # Calculate a simple match score based on keyword frequency
        matches = sum(1 for keyword in keywords if keyword in content)
        if matches > 0:
            # Add a synthetic similarity score based on matches
            result = summary.copy()
            # Add content field at top level for consistency with rest of system
            if not result.get("content") and content:
                result["content"] = summary["metadata"]["summary"] if "metadata" in summary and summary["metadata"] and "summary" in summary["metadata"] else ""
            result["title"] = summary.get("metadata", {}).get("timestamp", "No Date")
            result['similarity'] = matches / len(keywords) if keywords else 0
            results.append(result)
    
    # Sort by our synthetic similarity score
    results.sort(key=lambda x: x['similarity'], reverse=True)
    # Normalize results structure before returning
    return normalize_search_results(results[:15])  # Return top 15 results

def unified_search(query: str, 
                   embedding: List[float], 
                   top_k: int = 5, 
                   use_rag: bool = True,
                   model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    """
    Unified search function that combines vector search with optional RAG.
    
    Args:
        query: The user's text query
        embedding: The query embedding vector
        top_k: Number of results to return
        use_rag: Whether to use RAG to enhance results
        model: Which model to use for RAG (defaults to OLLAMA_MODEL from config)
        
    Returns:
        Dictionary containing search results and RAG response if applicable
    """
    logger.debug(f"Search query: '{query}', top_k={top_k}, use_rag={use_rag}")
    
    try:
        # Try keyword search first since we know it works reliably
        keyword_results = search_by_keywords(query)
        
        # Try vector search as well if we have an embedding
        vector_results = []
        if embedding is not None:
            try:
                raw_vector_results = search_summaries(embedding, top_k=top_k)
                
                # Log the raw structure before normalization to help debug
                if raw_vector_results and len(raw_vector_results) > 0:
                    logger.debug(f"Raw vector result keys: {list(raw_vector_results[0].keys())}")
                    
                # Normalize vector results
                vector_results = normalize_search_results(raw_vector_results)
                logger.info(f"Vector search found {len(vector_results)} results")
            except Exception as e:
                logger.error(f"Vector search failed: {str(e)}")
                # Continue with keyword results if vector search fails
        
        # Combine results if both methods returned something
        if keyword_results and vector_results:
            # Add source information to distinguish results
            for r in vector_results:
                r['source'] = 'vector'
            for r in keyword_results:
                r['source'] = 'keyword'
                
            # Combine and re-sort by similarity
            all_results = vector_results + keyword_results
            # Remove duplicates based on ID
            seen_ids = set()
            unique_results = []
            for result in all_results:
                if result.get('id') not in seen_ids:
                    seen_ids.add(result.get('id'))
                    unique_results.append(result)
            
            # Sort by similarity
            unique_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            results = unique_results[:top_k]
        elif keyword_results:
            results = keyword_results
        elif vector_results:
            results = vector_results
        else:
            return {"success": False, "message": "No results found", "raw_results": []}
        
        # Final error checking on results
        if not results:
            return {"success": False, "message": "No results found", "raw_results": []}
            
        # Ensure each result has the content field populated
        normalized_results = normalize_search_results(results)
        
        # Double check content exists in at least some results
        content_count = sum(1 for r in normalized_results if r.get('content'))
        if content_count == 0:
            logger.warning("No content found in any normalized results")
                    
        if use_rag:
            # Use RAG to enhance results
            try:
                rag_response = rag_search(query, normalized_results, model=model)
                return {
                    "success": True,
                    "raw_results": normalized_results,
                    "rag_response": rag_response
                }
            except Exception as e:
                logger.error(f"Error in RAG processing: {str(e)}")
                # Fall back to raw results if RAG fails
                return {
                    "success": True,
                    "raw_results": normalized_results,
                    "error": f"RAG processing failed: {str(e)}"
                }
        else:
            # Return raw results without RAG
            return {
                "success": True,
                "raw_results": normalized_results
            }
            
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return {"success": False, "message": f"Search error: {str(e)}", "raw_results": []}