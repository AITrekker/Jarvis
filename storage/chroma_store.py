"""
ChromaDB Integration Module

This module provides top-level functions for ChromaDB operations, serving as the main
entry point for vector database operations in the Jarvis application.

Role in the system:
- Re-exports key functions from specialized ChromaDB modules
- Provides backward compatibility for code using the original API
- Initializes ChromaDB when imported (unless in test mode)
- Handles adding, searching, and retrieving embeddings for summaries and transcripts
- Manages error handling and exceptions for ChromaDB operations

Used by various parts of the application that need to store or retrieve vector data.
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from setup.logger import logger
from storage.chroma.client import initialize_chroma as initialize_chroma_internal
from storage.chroma.client import chroma_client, is_test_mode, initialize_chroma
from storage.chroma import summaries_db, transcripts_db

# Re-export key classes for backwards compatibility
from storage.chroma.summaries_db import SummaryError
from storage.chroma.transcripts_db import TranscriptError

class ChromaDBError(Exception):
    """Exception raised for ChromaDB-related errors."""
    pass

# Re-export initialization function
def initialize_chroma(force=False):
    """Initialize ChromaDB client and collections."""
    return initialize_chroma_internal(force)

# Re-export key functions for backwards compatibility
def add_summary_embedding(embedding, summary_text, source_transcripts, timestamp=None):
    """Add a summary embedding to ChromaDB."""
    return summaries_db.add_summary(embedding, summary_text, source_transcripts, timestamp)

def search_summaries(query_embedding, top_k=5):
    """Search the summaries collection."""
    return summaries_db.search(query_embedding, top_k)

def get_all_summaries(limit=100):
    """Get all summaries from ChromaDB."""
    return summaries_db.get_all(limit)

def delete_summary_by_id(summary_id):
    """Delete a summary by ID and its related transcripts."""
    success = summaries_db.delete_by_id(summary_id)
    if success:
        # Try to delete related transcripts too
        # Update this reference to the renamed file
        transcripts_db.delete_related_to_summary(summary_id)
    return success

def get_all_transcripts(limit=1000):
    """Get all transcripts from ChromaDB."""
    # Update this reference to the renamed file
    return transcripts_db.get_all(limit)

def add_transcript(text, speaker="user", timestamp=None, embedding=None, metadata=None):
    """Add a transcript to ChromaDB."""
    # Update this reference to the renamed file
    return transcripts_db.add_transcript(text, speaker, timestamp, embedding, metadata)

# Only initialize at import if client is None
# Modified initialization logic
if not is_test_mode and chroma_client is None:
    initialize_chroma()