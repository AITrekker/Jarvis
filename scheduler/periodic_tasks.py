import time
import threading
from config import SUMMARY_INTERVAL_MIN
from summarizer.summarize import summarize_text
from storage.db import load_recent_transcripts

def summarize_job():
    print("Running periodic summarization job...")
    # TODO: Run summarization on recent transcripts

def start_scheduler():
    def run_scheduler():
        while True:
            summarize_job()
            time.sleep(SUMMARY_INTERVAL_MIN * 60)
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
