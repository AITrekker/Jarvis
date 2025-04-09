import time
import threading
from datetime import datetime, timedelta
from config import SUMMARY_INTERVAL_MIN
from utils.summarize import summarize_recent_transcripts
from setup.logger import logger

# Add this global variable at the top of periodic_tasks.py
_scheduler_thread = None
_stop_event = threading.Event()

def get_seconds_until_next_interval():
    """
    Calculate seconds until next interval based on the clock
    """
    now = datetime.now()
    
    # Calculate minutes into the current interval
    interval = SUMMARY_INTERVAL_MIN
    current_minute = now.minute % interval
    current_second = now.second
    
    # Calculate seconds until the next interval
    seconds_to_next = ((interval - current_minute) * 60) - current_second
    
    return max(seconds_to_next, 1)  # Ensure at least 1 second

def summarize_job():
    """
    Run the summarization job
    """
    print(f"\n==== SCHEDULED SUMMARY JOB [{datetime.utcnow().isoformat()}] ====")
    print(f"Running periodic summarization job (every {SUMMARY_INTERVAL_MIN} minutes)...")
    
    # Run the summarization on recent transcripts
    summary = summarize_recent_transcripts()
    
    if summary:
        print("\nSUMMARY OUTPUT:")
        print("-" * 50)
        print(summary)
        print("-" * 50)
    else:
        print("No summary was generated (likely no transcripts available)")
    
    print(f"==== SUMMARY JOB COMPLETED ====\n")

# Modify start_scheduler to store the thread and use the stop event
def start_scheduler():
    """
    Start the background thread for periodic summarization
    """
    global _scheduler_thread, _stop_event
    
    # Reset the stop event
    _stop_event.clear()
    
    def run_scheduler():
        print(f"Scheduler started. Will summarize every {SUMMARY_INTERVAL_MIN} minutes.")
        
        # Calculate time until next interval instead of fixed delay
        seconds_to_wait = get_seconds_until_next_interval()
        next_run = datetime.now() + timedelta(seconds=seconds_to_wait)
        print(f"Next summarization scheduled at: {next_run.strftime('%H:%M:%S')}")
        
        # Wait until first interval or until stopped
        while not _stop_event.wait(timeout=min(seconds_to_wait, 1.0)):
            seconds_to_wait -= 1.0
            if seconds_to_wait <= 0:
                break
            
        # Main loop
        while not _stop_event.is_set():
            try:
                summarize_job()
            except Exception as e:
                print(f"Error in summarization job: {e}")
                
            # Calculate time until next interval
            seconds_to_wait = get_seconds_until_next_interval()
            next_run = datetime.now() + timedelta(seconds=seconds_to_wait)
            print(f"Next summarization scheduled at: {next_run.strftime('%H:%M:%S')}")
            
            # Sleep until next interval or until stopped
            while not _stop_event.wait(timeout=min(seconds_to_wait, 1.0)):
                seconds_to_wait -= 1.0
                if seconds_to_wait <= 0:
                    break
    
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_thread = threading.Thread(target=run_scheduler)
        _scheduler_thread.daemon = True  # Still keep as daemon
        _scheduler_thread.start()
    
    return _scheduler_thread

# Add this function to stop the scheduler
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
