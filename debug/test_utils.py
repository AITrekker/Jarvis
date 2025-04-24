"""
Test Debugging Utilities

This module contains utilities to help with test debugging and cleanup.
"""

import os
import glob
import shutil
import tempfile
from datetime import datetime

def create_test_summary_dir():
    """Create a temporary directory for test summaries
    
    Returns:
        str: Path to temporary test directory
    """
    test_dir = tempfile.mkdtemp(prefix="jarvis_test_summaries_")
    return test_dir

def cleanup_test_summaries(summary_dir=None):
    """Clean up test summary files
    
    Args:
        summary_dir: Optional specific directory to clean. If None, uses SUMMARY_DIR
    """
    from config import SUMMARY_DIR
    
    target_dir = summary_dir if summary_dir else SUMMARY_DIR
    
    if not os.path.exists(target_dir):
        return
        
    # Find all summary files in the target directory
    pattern = os.path.join(target_dir, "summary_*.json")
    summary_files = glob.glob(pattern)
    
    # Remove each summary file
    for file_path in summary_files:
        try:
            os.remove(file_path)
            print(f"Removed test summary: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error removing test summary {file_path}: {e}")
            
    # If this was a temporary directory we created, remove it completely
    if summary_dir and summary_dir != SUMMARY_DIR:
        try:
            shutil.rmtree(summary_dir)
            print(f"Removed test summary directory: {summary_dir}")
        except Exception as e:
            print(f"Error removing test summary directory {summary_dir}: {e}")