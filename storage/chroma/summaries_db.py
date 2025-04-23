"""
Operations for managing summary documents in ChromaDB.
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from setup.logger import logger
from storage.chroma.client import get_collections, is_test_mode

class SummaryError(Exception):
    """Exception for summary-related errors."""
    pass

def add_summary(
    embedding: List[float], 
    summary_text: str, 
    source_transcripts: List[Dict[str, Any]], 
    timestamp: Optional[str] = None
) -> str:
    """
    Add a summary embedding to ChromaDB.
    
    Args:
        embedding: The vector embedding of the summary.
        summary_text: The text of the summary.
        source_transcripts: Source transcripts used to generate the summary.
        timestamp: Optional timestamp. Current time used if not provided.
        
    Returns:
        The ID of the added embedding.
    """
    summaries_collection, _ = get_collections()
    
    # Handle test mode or initialization failures
    if is_test_mode or summaries_collection is None:
        if is_test_mode:
            logger.debug("Test mode: Returning dummy summary ID")
            return str(uuid.uuid4())
        
        if summaries_collection is None:
            logger.error("Could not initialize ChromaDB collections")
            return str(uuid.uuid4())
    
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = datetime.now().isoformat()
        
    # Generate a unique ID for this embedding
    embedding_id = str(uuid.uuid4())
    logger.debug(f"Generated summary ID: {embedding_id}")
    
    # Prepare metadata
    metadata = {
        "summary": summary_text,
        "timestamp": timestamp,
        "source_count": len(source_transcripts),
        "first_transcript_time": source_transcripts[0]["timestamp"] if source_transcripts else None,
        "last_transcript_time": source_transcripts[-1]["timestamp"] if source_transcripts else None
    }
    
    # Store full source transcripts as document text
    document = json.dumps(source_transcripts)
    
    try:
        # Add to ChromaDB
        summaries_collection.add(
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata],
            ids=[embedding_id]
        )
        #logger.info(f"Added summary embedding to ChromaDB with ID: {embedding_id}")
        logger.debug(f"Summary metadata: {metadata}")
        return embedding_id
    except Exception as e:
        logger.error(f"Error adding summary embedding to ChromaDB: {e}", exc_info=True)
        return None

def get_all(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all summaries stored in ChromaDB, up to the specified limit.
    
    Args:
        limit: Maximum number of summaries to return.
        
    Returns:
        List of dictionaries containing the summaries.
    """
    summaries_collection, _ = get_collections()
    
    if summaries_collection is None:
        logger.error("ChromaDB collections not initialized")
        return []
    
    try:
        logger.debug(f"Retrieving up to {limit} summaries from ChromaDB")
        
        # Get all embeddings
        results = summaries_collection.get(limit=limit)
        
        # Format results for easier processing
        formatted_results = []
        for i in range(len(results["ids"])):
            formatted_result = {
                "id": results["ids"][i],
                "metadata": results["metadatas"][i],
                "source_transcripts": json.loads(results["documents"][i]) if results["documents"][i] else []
            }
            formatted_results.append(formatted_result)
            
        # Add this log line to match the transcript retrieval log format
        logger.info(f"Retrieved {len(formatted_results)} summaries from ChromaDB")
            
        return formatted_results
    except Exception as e:
        logger.error(f"Error getting summaries from ChromaDB: {e}", exc_info=True)
        return []

def search(query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search the ChromaDB summaries collection for the most relevant results.
    
    Args:
        query_embedding: The embedding to search with
        top_k: Number of results to return
        
    Returns:
        List of dictionaries with search results
    """
    summaries_collection, _ = get_collections()
    
    if summaries_collection is None:
        logger.error("ChromaDB collections not initialized")
        return []
    
    try:
        logger.debug(f"Searching summaries with top_k={top_k}")
        
        # Query ChromaDB
        results = summaries_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        # Format the results
        formatted_results = []
        for i in range(len(results["documents"][0])):
            formatted_results.append({
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        
        logger.debug(f"Found {len(formatted_results)} summary results")
        return formatted_results
    except Exception as e:
        logger.error(f"Error during summary search: {str(e)}", exc_info=True)
        return []

def delete_by_id(summary_id: str) -> bool:
    """
    Delete a summary by ID.
    
    Args:
        summary_id: The ID of the summary to delete
    
    Returns:
        bool: True if deletion was successful
    """
    summaries_collection, _ = get_collections()
    
    logger.info(f"Deleting summary with ID: {summary_id}")
    
    # Try with existing collection first
    if summaries_collection is not None:
        try:
            summaries_collection.delete(ids=[summary_id])
            logger.info(f"Successfully deleted summary {summary_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting summary: {str(e)}", exc_info=True)
    
    # If we get here, try a fallback method
    try:
        import chromadb
        import config
        
        logger.debug("Using fallback method to delete summary")
        client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        collection = client.get_collection(name="summaries")
        collection.delete(ids=[summary_id])
        logger.info(f"Successfully deleted summary {summary_id} using fallback method")
        return True
    except Exception as e:
        logger.error(f"Error in fallback deletion for summary: {str(e)}", exc_info=True)
        raise SummaryError(f"Failed to delete conversation: {str(e)}")