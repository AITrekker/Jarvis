from mic_stream.recorder import transcribe_from_mic
from scheduler.periodic_tasks import start_scheduler

if __name__ == "__main__":
    start_scheduler()
    transcribe_from_mic()
