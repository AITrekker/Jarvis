from mic_stream.recorder import transcribe_from_mic
from scheduler.periodic_tasks import start_scheduler, stop_scheduler
from setup.setup import check_dependencies
import config  # Import config to ensure platform detection runs
from setup.logger import logger  

def main():
    """Main function to run the Jarvis voice transcription system."""
    print("Starting Jarvis voice transcription system...")
    logger.info("Starting Jarvis voice transcription system...")
    
    # Check dependencies
    check_dependencies()
    
    # Start the scheduler for periodic tasks
    scheduler = start_scheduler()
    
    try:
        # Start transcribing from microphone
        transcribe_from_mic()
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        stop_scheduler()
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        stop_scheduler()

if __name__ == "__main__":
    main()
