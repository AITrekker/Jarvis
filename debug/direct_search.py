import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.chroma_store import get_client
from setup.logger import logger

def direct_keyword_search(query_terms):
    """Search directly in ChromaDB for specific terms"""
    try:
        client = get_client()
        collections = client.list_collections()
        
        print(f"Found {len(collections)} collections")
        for collection in collections:
            print(f"Collection: {collection.name}, count: {collection.count()}")
            
            # Try direct term search
            for term in query_terms:
                results = collection.query(
                    query_texts=[term],
                    n_results=5
                )
                
                print(f"\nResults for '{term}' in {collection.name}:")
                if results["documents"] and len(results["documents"][0]) > 0:
                    for i, doc in enumerate(results["documents"][0]):
                        print(f"Result {i+1}:\n{doc[:300]}...\n")
                else:
                    print("No results found")
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Search for terms related to periodic table
    direct_keyword_search(["periodic table", "elements", "chemical", "fluorine"])