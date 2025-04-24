"""
ChromaDB Integration Package

This package provides ChromaDB integration for the Jarvis application,
organizing vector storage functionality into specialized modules.

Role in the system:
- Exposes key ChromaDB functionality to the rest of the application
- Re-exports important classes and functions for easier imports
- Separates concerns between client initialization, summary operations, and transcript operations
- Provides custom exception types for ChromaDB-related errors

Used by higher-level storage modules that need vector database functionality.
"""
from storage.chroma.client import initialize_chroma
from storage.chroma.summaries_db import SummaryError
from storage.chroma.transcripts_db import TranscriptError