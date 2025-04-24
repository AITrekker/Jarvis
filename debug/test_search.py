"""
Test script for the search functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search.search_engine import search_by_keywords, unified_search
import json

def test_keyword_search():
    """Test the keyword search with various queries"""
    test_queries = [
        "periodic table",
        "elements",
        "chemical",
        "squirrels",  # From the transcript about shoes in trees
        "shawl machine",  # From another transcript
        "Chevy engine"    # From another transcript
    ]
    
    print("Testing keyword search...")
    for query in test_queries:
        print(f"\n=== Search for: '{query}' ===")
        results = search_by_keywords(query)
        print(f"Found {len(results)} results")
        
        for i, result in enumerate(results[:3]):  # Show top 3 results
            print(f"\nResult {i+1}: (similarity: {result.get('similarity', 'N/A'):.2f})")
            if "metadata" in result and "summary" in result["metadata"]:
                summary = result["metadata"]["summary"]
                print(f"Summary: {summary[:200]}...")
            elif "content" in result:
                print(f"Content: {result['content'][:200]}...")
            else:
                print("No content found in this result")

if __name__ == "__main__":
    test_keyword_search()