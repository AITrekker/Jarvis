"""
Operations for managing transcript documents in ChromaDB.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from setup.logger import logger
from storage.chroma.client import get_collections

class TranscriptError(Exception):
    """Exception for transcript-related errors."""
    pass

def get_all(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Get all transcripts stored in ChromaDB, up to the specified limit.
    
    Args:
        limit: Maximum number of transcripts to return.
        
    Returns:
        List of dictionaries containing the transcripts.
    """
    _, transcripts_collection = get_collections()
    
    if transcripts_collection is None:
        logger.error("ChromaDB transcripts collection not initialized")
        return []
    
    try:
        logger.debug(f"Retrieving up to {limit} transcripts from ChromaDB")
        
        # Get all transcripts with their metadata
        results = transcripts_collection.get(limit=limit)
        
        # Format results for easier processing
        formatted_results = []
        for i in range(len(results["ids"])):
            formatted_result = {
                "id": results["ids"][i],
                "document": results["documents"][i],
                "metadata": results["metadatas"][i]
            }
            formatted_results.append(formatted_result)
            
        logger.info(f"Retrieved {len(formatted_results)} transcripts from ChromaDB")
        return formatted_results
    except Exception as e:
        logger.error(f"Error getting transcripts from ChromaDB: {e}", exc_info=True)
        return []

def add_transcript(
    text: str,
    speaker: str = "user",
    timestamp: Optional[str] = None,
    embedding: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add a transcript entry to ChromaDB.
    
    Args:
        text: The transcript text
        speaker: Who said this (user/assistant/system)
        timestamp: Optional timestamp (current time used if None)
        embedding: Optional vector embedding of the text
        metadata: Additional metadata to store
        
    Returns:
        The ID of the added transcript
    """
    _, transcripts_collection = get_collections()
    
    if transcripts_collection is None:
        logger.error("ChromaDB transcripts collection not initialized")
        return None
    
    if timestamp is None:
        timestamp = datetime.now().isoformat()
        
    # Generate a unique ID for this transcript
    transcript_id = str(uuid.uuid4())
    
    # Prepare metadata
    meta = metadata or {}
    meta.update({
        "speaker": speaker,
        "timestamp": timestamp,
        "length": len(text)
    })
    
    try:
        # Add to ChromaDB
        if embedding:
            transcripts_collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[meta],
                ids=[transcript_id]
            )
        else:
            transcripts_collection.add(
                documents=[text],
                metadatas=[meta],
                ids=[transcript_id]
            )
            
        logger.debug(f"Added transcript to ChromaDB with ID: {transcript_id}")
        return transcript_id
    except Exception as e:
        logger.error(f"Error adding transcript to ChromaDB: {e}", exc_info=True)
        return None

def delete_related_to_summary(summary_id: str) -> int:
    """
    Delete transcripts related to a specific summary.
    
    Args:
        summary_id: The ID of the summary
        
    Returns:
        int: Number of transcripts deleted
    """
    _, transcripts_collection = get_collections()
    
    if transcripts_collection is None:
        logger.warning("Transcripts collection is not initialized")
        return 0
    
    try:
        logger.debug(f"Finding transcripts related to summary {summary_id}")
        
        # Get all transcript IDs
        transcript_results = transcripts_collection.get()
        
        # Check if we got any results
        if not transcript_results or len(transcript_results["ids"]) == 0:
            logger.info("No transcripts found in collection")
            return 0
        
        transcript_ids = transcript_results["ids"]
        logger.debug(f"Found {len(transcript_ids)} total transcripts in collection")
        
        # Find related transcripts by ID pattern
        related_transcript_ids = [
            t_id for t_id in transcript_ids 
            if summary_id in t_id  # Simple matching - if summary ID is part of transcript ID
        ]
        
        logger.debug(f"Found {len(related_transcript_ids)} transcript(s) related to summary {summary_id}")
        
        if related_transcript_ids:
            transcripts_collection.delete(ids=related_transcript_ids)
            logger.info(f"Deleted {len(related_transcript_ids)} related transcript entries")
            return len(related_transcript_ids)
        
        logger.info("No related transcripts found with matching ID pattern")
        return 0
        
    except Exception as e:
        logger.error(f"Error deleting related transcripts: {str(e)}", exc_info=True)
        return 0