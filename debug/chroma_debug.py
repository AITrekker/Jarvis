"""
ChromaDB debugging tool - helps identify issues with data storage
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.chroma_store import get_all_summaries
import json
import chromadb
import os

def debug_chromadb_data():
    """Debug and dump raw ChromaDB data"""
    # Get database path - assumes default location
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma")
    if not os.path.exists(db_path):
        print(f"ChromaDB path doesn't exist: {db_path}")
        # Try to find where it might be located
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            print(f"Contents of data directory: {os.listdir(data_dir)}")
        return
        
    print(f"Found ChromaDB at: {db_path}")
    
    # Try to create direct client
    try:
        client = chromadb.PersistentClient(path=db_path)
        print(f"Successfully connected to ChromaDB")
        
        # List collections
        collections = client.list_collections()
        print(f"Found {len(collections)} collections: {[c.name for c in collections]}")
        
        # Inspect each collection
        for collection in collections:
            print(f"\n======== Collection: {collection.name} ========")
            print(f"Count: {collection.count()}")
            
            # Get sample data
            if collection.count() > 0:
                print("Fetching all data from collection...")
                data = collection.get()
                
                # Print first item's structure
                if data and len(data["ids"]) > 0:
                    print(f"Sample item structure:")
                    for key in data:
                        if isinstance(data[key], list):
                            print(f"  {key}: {type(data[key][0])} ({len(data[key])} items)")
                            if key == "documents" and data[key]:
                                # Check if documents contain content
                                print(f"  First document length: {len(data['documents'][0]) if data['documents'][0] else 0}")
                                print(f"  First document preview: {data['documents'][0][:100]}..." if data['documents'][0] else "Empty")
                        else:
                            print(f"  {key}: {type(data[key])}")
                    
                    # Check metadatas
                    if "metadatas" in data and data["metadatas"]:
                        print(f"  Metadata keys in first item: {list(data['metadatas'][0].keys()) if data['metadatas'][0] else 'None'}")
                        
                        # If content is in metadata, highlight that
                        if data["metadatas"][0] and "content" in data["metadatas"][0]:
                            content_length = len(data["metadatas"][0]["content"])
                            print(f"  Content found in metadata! Length: {content_length}")
                            print(f"  Content preview: {data['metadatas'][0]['content'][:100]}...")
                
                # Create test summary with actual content
                print("\nCreating a test summary with real content to see if it stores properly...")
                test_summary = {
                    "title": "Periodic Table Test",
                    "date": "2025-04-23",
                    "content": "The periodic table shows elements with their chemical properties. Elements like hydrogen, helium, lithium, and fluorine are organized by atomic number. This is a test entry to verify storage.",
                    "metadata": {"source": "diagnostic_test"}
                }
                
                # Store the test summary - this will use your actual storage logic
                # from search_engine import unified_search
                # result = unified_search("periodic table", None, use_rag=False)
                # print(f"Search result after adding test data: {result}")
                
    except Exception as e:
        print(f"Error accessing ChromaDB directly: {str(e)}")
    
    # Now check what get_all_summaries returns
    print("\n======== Using get_all_summaries() ========")
    try:
        summaries = get_all_summaries()
        print(f"Retrieved {len(summaries)} summaries")
        
        if summaries:
            print(f"First summary keys: {list(summaries[0].keys())}")
            
            # Look for content - check all possible field names
            content_fields = ["content", "text", "document", "summary", "transcript"]
            found_content = False
            
            for summary in summaries[:5]:  # Check first 5 summaries
                for field in content_fields:
                    if field in summary and summary[field]:
                        print(f"Found content in field '{field}', length: {len(summary[field])}")
                        print(f"Content preview: {summary[field][:100]}...")
                        found_content = True
                        break
            
            if not found_content:
                print("No content found in standard fields. Raw data of first summary:")
                print(json.dumps(summaries[0], indent=2))
    except Exception as e:
        print(f"Error in get_all_summaries: {str(e)}")

if __name__ == "__main__":
    debug_chromadb_data()