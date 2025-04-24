"""
Command Line Interface for Search

This module provides a standalone command-line interface for searching through
conversation transcripts and summaries stored in ChromaDB.

Role in the system:
- Offers direct command-line access to search functionality
- Validates ChromaDB data availability
- Provides interactive search experience
- Formats results for terminal display

This is a standalone utility that can be run directly for command-line searching
without needing to start the web interface.
"""

import sys
import os

# Add the parent directory to path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Fix the imports
from utils.summarize import generate_embedding
from storage.chroma_store import search_summaries, initialize_chroma  # Add initialize_chroma
from setup.logger import logger
from search.search import search_transcripts

# Force ChromaDB initialization when running CLI
initialize_chroma(force=True)

def search_by_text(query_text, top_k=5):
    """
    Search for summaries similar to the query text.
    
    Args:
        query_text: The text to search for.
        top_k: Number of results to return.
        
    Returns:
        List of dictionaries containing the search results.
    """
    # Generate embedding for the query text
    query_embedding = generate_embedding(query_text)
    
    # Search using the embedding
    results = search_summaries(query_embedding, top_k)
    
    return results

def check_chroma_data():
    """Check if ChromaDB has any data and inform the user."""
    from storage.chroma_store import get_all_summaries
    
    try:
        summaries = get_all_summaries(limit=1)
        if not summaries:
            print("\n⚠️  No data found in ChromaDB yet!")
            print("You need to run the summarizer to generate some summaries before searching.")
            print("The search will only return results after summaries have been generated and stored.\n")
        else:
            print(f"\n✅ Found {len(summaries)} summaries in ChromaDB.\n")
    except Exception as e:
        print(f"\n❌ Error checking ChromaDB data: {e}\n")

def main():
    """
    Simple CLI for searching summaries.
    """
    print("\nJarvis Semantic Search")
    print("======================\n")
    
    # Check if ChromaDB has data
    check_chroma_data()
    
    while True:
        query = input("Enter your search query (or type 'exit' to quit): ")
        
        if query.lower() == 'exit':
            print("Goodbye!")
            break
            
        results = search_transcripts(query)
        
        if not results:
            print("\nNo results found. Try another query.\n")
            continue
            
        print(f"\nFound {len(results)} results:\n")
        
        for i, result in enumerate(results):
            print(f"Result #{i+1}:")
            print(f"  Summary: {result['metadata']['summary']}")
            print(f"  Time: {result['metadata'].get('timestamp', 'N/A')}")
            print(f"  Source count: {result['metadata'].get('source_count', 'N/A')}")
            print()
    
if __name__ == "__main__":
    main()