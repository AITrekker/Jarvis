"""
Debug Logging Configuration

This module provides enhanced logging capabilities for debugging purposes.
"""

import os
import logging
from datetime import datetime

def configure_debug_logging(debug=False):
    """Configure logging level based on debug flag.
    
    Args:
        debug (bool): Whether to enable debug-level logging
        
    Returns:
        logging.Logger: Configured logger instance
    """
    from config import LOG_DIR
    
    # Clear existing handlers to allow reconfiguration
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(LOG_DIR, "jarvis.log"))
        ]
    )
    logger = logging.getLogger(__name__)
    logger.debug("Debug mode enabled: Verbose logging activated." if debug else "Logging set to INFO level.")
    
    return logger

def get_debug_logger(name):
    """Get a logger configured for debug use with the specified name
    
    Args:
        name (str): Logger name, typically __name__
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)