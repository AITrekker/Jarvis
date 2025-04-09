import logging
import os
from datetime import datetime

# Import config values
from config import LOG_LEVEL, LOG_DIR

def setup_logging():
    """Set up logging configuration"""
    # Create logs directory if it doesn't exist
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Clear any existing handlers to avoid duplicate logs
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Create file handler that logs to a new file each day
    log_file = os.path.join(LOG_DIR, f"jarvis_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.FileHandler(log_file)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

def set_log_level(level):
    """
    Dynamically change the logging level.
    
    Args:
        level: A logging level like logging.DEBUG, logging.INFO, etc.
    """
    logger = logging.getLogger()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
    
    logger.info(f"Log level changed to: {logging.getLevelName(level)}")

# Get the logger
logger = setup_logging()