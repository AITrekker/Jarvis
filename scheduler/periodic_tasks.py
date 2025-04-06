import time
import threading
from datetime import datetime
from config import SUMMARY_INTERVAL_MIN
from summarizer.summarize import summarize_recent_transcripts

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

def start_scheduler():
    """
    Start the background thread for periodic summarization
    """
    def run_scheduler():
        print(f"Scheduler started. Will summarize every {SUMMARY_INTERVAL_MIN} minutes.")
        
        # Initial delay to allow some transcripts to accumulate
        initial_delay = min(5 * 60, SUMMARY_INTERVAL_MIN * 30)  # 5 minutes or 1/2 interval
        time.sleep(initial_delay)
        
        while True:
            try:
                summarize_job()
            except Exception as e:
                print(f"Error in summarization job: {e}")
                
            # Sleep until next interval
            time.sleep(SUMMARY_INTERVAL_MIN * 60)
    
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    return thread
