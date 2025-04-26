"""
Periodic Task Scheduler Module

This module provides functionality for scheduling and executing periodic tasks
such as summarization of conversation transcripts.

Role in the system:
- Sets up the scheduler for periodic execution of tasks
- Defines job functions that run on schedule
- Manages the summarization workflow on a regular basis
- Handles errors in scheduled jobs with appropriate logging
- Provides proper cleanup after job execution

Used during application startup to initialize background tasks that run
periodically while the application is active.
"""

import time
import threading
from datetime import datetime, timedelta
from config import SUMMARY_INTERVAL_MIN
from utils.summarize import summarize_recent_transcripts
# Remove the delete_transcripts_in_time_range import since it's now used in summarize.py
from setup.logger import logger

# Global variables for scheduler
_scheduler_thread = None
_stop_event = threading.Event()

def get_seconds_until_next_interval():
    """Calculate seconds until next interval based on the clock"""
    now = datetime.now()
    current_minute = now.minute % SUMMARY_INTERVAL_MIN
    return ((SUMMARY_INTERVAL_MIN - current_minute) * 60) - now.second

def wait_until_next_interval():
    """Wait until the next interval or until stopped"""
    seconds_to_wait = get_seconds_until_next_interval()
    next_run = datetime.now() + timedelta(seconds=seconds_to_wait)
    print(f"Next summarization scheduled at: {next_run.strftime('%H:%M:%S')}")
    
    while not _stop_event.wait(timeout=min(seconds_to_wait, 1.0)):
        seconds_to_wait -= 1.0
        if seconds_to_wait <= 0:
            break
    
    return _stop_event.is_set()  # Return True if we should stop

def summarize_job():
    """
    Run the summarization job
    """
    print(f"\n==== SCHEDULED SUMMARY JOB [{datetime.utcnow().isoformat()}] ====")
    print(f"Running periodic summarization job (every {SUMMARY_INTERVAL_MIN} minutes)...")
    
    try:
        # Run the summarization on recent transcripts
        # Deletion is now handled inside summarize_recent_transcripts()
        summary = summarize_recent_transcripts()
        
        if summary and not summary.startswith("Error"):
            print("\nSUMMARY OUTPUT:")
            print("-" * 50)
            print(summary)
            print("-" * 50)
            # No need for transcript deletion here as it's now handled in summarize_recent_transcripts
        else:
            error_msg = summary if summary else "No summary generated"
            print(f"⚠️ No valid summary was generated: {error_msg}")
            # Warning about not deleting transcripts is now handled in summarize_recent_transcripts
    except Exception as e:
        logger.error(f"Error during periodic summarization job: {e}")
        print(f"❌ Error during periodic summarization: {e}")
    
    print(f"==== SUMMARY JOB COMPLETED ====\n")

def start_scheduler():
    """Start the background thread for periodic summarization"""
    global _scheduler_thread, _stop_event
    
    # Reset the stop event
    _stop_event.clear()
    
    def run_scheduler():
        print(f"Scheduler started. Will summarize every {SUMMARY_INTERVAL_MIN} minutes.")
        
        # Wait until first interval
        if wait_until_next_interval():
            return  # Stop if requested
            
        # Main loop
        while not _stop_event.is_set():
            try:
                summarize_job()
            except Exception as e:
                print(f"Error in summarization job: {e}")
                
            # Wait until next interval
            if wait_until_next_interval():
                break  # Stop if requested
    
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_thread = threading.Thread(target=run_scheduler)
        _scheduler_thread.daemon = True
        _scheduler_thread.start()
    
    return _scheduler_thread

def stop_scheduler():
    """
    Stop the background scheduler thread
    """
    global _stop_event, _scheduler_thread
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        print("Stopping scheduler...")
        _stop_event.set()
        _scheduler_thread.join(timeout=2.0)  # Wait for thread to finish, but with timeout
        
        if _scheduler_thread.is_alive():
            print("Warning: Scheduler thread did not terminate cleanly")
        else:
            print("Scheduler stopped successfully")
    else:
        print("No scheduler running")
