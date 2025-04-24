"""
Diagnostic tools for the search system.
Helps identify issues with ChromaDB storage and embeddings.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.chroma_store import search_summaries, get_all_summaries
from setup.logger import logger
import json

# Remove the ChromaDB direct inspection functions that depend on get_client
# We'll focus on functions that use your existing API

def inspect_summaries():
    """
    Inspect summaries stored in ChromaDB.
    
    Returns:
        Dict containing information about stored summaries
    """
    try:
        summaries = get_all_summaries()
        
        result = {
            "summary_count": len(summaries),
            "summaries": []
        }
        
        # Analyze summaries and collect metadata
        for summary in summaries:
            summary_info = {
                "title": summary.get("title", "No Title"),
                "date": summary.get("date", "Unknown Date"),
                "content_length": len(summary.get("content", "")),
                "content_preview": summary.get("content", "")[:150] + "..." if len(summary.get("content", "")) > 150 else summary.get("content", ""),
                "has_metadata": bool(summary.get("metadata", {})),
                "keys": list(summary.keys())
            }
            result["summaries"].append(summary_info)
            
        return result
        
    except Exception as e:
        logger.error(f"Error inspecting summaries: {str(e)}")
        return {"error": str(e)}

def search_text_in_summaries(query_terms):
    """
    Search for specific text in summary content.
    
    Args:
        query_terms: List of terms to search for
        
    Returns:
        Dict with matching summaries for each term
    """
    try:
        summaries = get_all_summaries()
        print(f"Retrieved {len(summaries)} summaries for searching")
        
        results = {}
        
        # For each search term, find matching summaries
        for term in query_terms:
            term_lower = term.lower()
            matching = []
            
            for summary in summaries:
                content = summary.get("content", "").lower()
                if term_lower in content:
                    matching.append({
                        "title": summary.get("title", "No Title"),
                        "date": summary.get("date", "Unknown Date"),
                        "content_preview": summary.get("content", "")[:200] + "..." if len(summary.get("content", "")) > 200 else summary.get("content", ""),
                        "position": content.find(term_lower),
                        "context": content[max(0, content.find(term_lower)-50):content.find(term_lower)+len(term)+50]
                    })
            
            results[term] = matching
            print(f"Found {len(matching)} matches for '{term}'")
            
        return results
        
    except Exception as e:
        logger.error(f"Error in text search: {str(e)}")
        return {"error": str(e)}

def analyze_embedding_search(query_term, embedding=None):
    """
    Analyze vector search results for a query.
    
    Args:
        query_term: The query string
        embedding: Optional embedding vector (if None, assumes the search_summaries function handles embedding)
        
    Returns:
        Dict with search results and analysis
    """
    try:
        # If we need to supply an embedding, we'd generate it here
        # Since your search_summaries may expect an embedding directly, we'll just pass None for now
        # and assume the function handles embedding generation
        
        results = search_summaries(embedding, top_k=10)
        
        analysis = {
            "query": query_term,
            "result_count": len(results),
            "results": []
        }
        
        # Analyze each result
        for i, result in enumerate(results):
            result_info = {
                "rank": i+1,
                "title": result.get("title", "No Title"),
                "date": result.get("date", "Unknown Date"),
                "similarity": result.get("similarity", result.get("distance", "N/A")),
                "content_preview": result.get("content", "")[:150] + "..." if len(result.get("content", "")) > 150 else result.get("content", "")
            }
            analysis["results"].append(result_info)
            
        return analysis
        
    except Exception as e:
        logger.error(f"Error in embedding search analysis: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # When run directly, inspect summaries
    print("===== SUMMARY INSPECTION =====")
    summaries_info = inspect_summaries()
    print(f"Found {summaries_info.get('summary_count', 0)} summaries")
    
    # Print the titles and dates of all summaries
    if summaries_info.get('summaries'):
        print("\nAll summaries:")
        for i, summary in enumerate(summaries_info['summaries']):
            print(f"{i+1}. {summary['title']} ({summary['date']}) - {summary['content_length']} chars")
    
    # Search for specific text
    print("\n===== TEXT SEARCH =====")
    search_results = search_text_in_summaries(["periodic table", "elements", "chemical", "fluorine"])
    
    # Print matches for each term
    for term, matches in search_results.items():
        print(f"\nMatches for '{term}':")
        for i, match in enumerate(matches):
            print(f"{i+1}. {match['title']} ({match['date']})")
            print(f"   Context: ...{match['context']}...")