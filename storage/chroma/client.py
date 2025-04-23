"""
ChromaDB client initialization and management.
"""
import os
import sys
from typing import Tuple, Optional
from setup.logger import logger
import config

# Detection for test mode
is_test_mode = 'pytest' in sys.modules or any(arg.endswith('unittest') for arg in sys.argv)

# Global client and collections - accessible from outside
chroma_client = None
summaries_collection = None
transcripts_collection = None

# Add this for tracking if initialization was attempted
_initialization_attempted = False

# Add this to cache between Streamlit reruns
_streamlit_session_key = "chroma_client_initialized"

def get_client(force_init: bool = False):
    """Get the ChromaDB client, initializing if needed."""
    global chroma_client
    
    if chroma_client is None or force_init:
        initialize_chroma(force=force_init)
    
    return chroma_client

def get_collections() -> Tuple[Optional[object], Optional[object]]:
    """Get the collections, initializing if needed."""
    global summaries_collection, transcripts_collection
    
    if summaries_collection is None or transcripts_collection is None:
        initialize_chroma()
    
    return summaries_collection, transcripts_collection

def initialize_chroma(force: bool = False) -> bool:
    """
    Initialize ChromaDB client and collections.
    
    Args:
        force: If True, reinitialize even if already initialized
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    global chroma_client, summaries_collection, transcripts_collection, _initialization_attempted
    
    # Enhanced Streamlit detection and caching
    try:
        # Check if we're running in Streamlit
        import streamlit as st
        
        # Use Streamlit's session state to track initialization
        if not force and "chroma_client_initialized" in st.session_state:
            logger.debug("Using previously initialized ChromaDB client from Streamlit session state")
            return True
            
    except ImportError:
        # Not running in Streamlit, continue with normal flow
        pass
    
    # Skip if already attempted unless forced
    if _initialization_attempted and not force:
        if chroma_client is not None:
            logger.debug("ChromaDB client already initialized")
            return True
        else:
            logger.debug("ChromaDB initialization previously failed, skipping")
            return False
    
    # Skip initialization in test mode unless forced
    if is_test_mode and not force:
        logger.debug("Running in test mode - skipping ChromaDB initialization")
        return False
    
    # Set flag that initialization was attempted
    _initialization_attempted = True
    
    try:
        # Import here to avoid import issues in tests
        import chromadb
        
        # Create directory for database if it doesn't exist
        os.makedirs(config.CHROMA_DIR, exist_ok=True)
        logger.debug(f"Using ChromaDB directory: {config.CHROMA_DIR}")
        
        # Initialize ChromaDB client with telemetry disabled
        #logger.info("Initializing ChromaDB client...")
        chroma_client = chromadb.PersistentClient(
            path=config.CHROMA_DIR,
            settings=chromadb.Settings(anonymized_telemetry=False)
        )
        
        # Initialize collections
        summaries_collection = _initialize_collection("summaries")
        transcripts_collection = _initialize_collection("transcripts")
        
        # Store in Streamlit session state if available
        try:
            import streamlit as st
            st.session_state["chroma_client_initialized"] = True
            logger.debug("Stored ChromaDB initialization state in Streamlit session")
        except (ImportError, AttributeError):
            pass
            
        #logger.info("ChromaDB initialization complete")
        return True
            
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}", exc_info=True)
        return False

def _initialize_collection(name: str):
    """Helper to initialize a collection."""
    global chroma_client
    
    try:
        logger.debug(f"Attempting to get existing '{name}' collection...")
        collection = chroma_client.get_collection(name=name)
        #logger.info(f"Loaded existing '{name}' collection")
        return collection
    except Exception as e:
        logger.debug(f"Creating new '{name}' collection: {e}")
        collection = chroma_client.create_collection(name=name)
        #logger.info(f"Created new '{name}' collection")
        return collection

# Initialize by default unless in test mode
if not is_test_mode:
    initialize_chroma()