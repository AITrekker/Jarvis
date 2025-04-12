import argparse
import subprocess
import sys
import os

from config import (
    PROJECT_ROOT, logger, ENV_VARS  # Removed set_environment_variables
)

from utils.periodic_tasks import start_scheduler, stop_scheduler
from utils.recorder import transcribe_from_mic
from setup.setup import check_dependencies  # Import check_dependencies

def display_banner():
    """Display ASCII art banner."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║        ██╗  █████╗  ██████╗  ██╗   ██╗ ██╗ ███████╗        ║
    ║        ██║ ██╔══██╗ ██╔══██╗ ██║   ██║ ██║ ██╔════╝        ║
    ║        ██║ ███████║ ██████╔╝ ██║   ██║ ██║ ███████╗        ║
    ║        ██║ ██╔══██║ ██╔══██╗ ╚██╗ ██╔╝ ██║ ╚════██║        ║
    ║     █████║ ██║  ██║ ██║  ██║  ╚████╔╝  ██║ ███████║        ║
    ║     ╚════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝   ╚═══╝   ╚═╝ ╚══════╝        ║
    ║                                                            ║
    ║   Your AI assistant that listens, remembers, and recalls   ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)

def run_jarvis(mode="shell"):
    """Main entry point for Jarvis."""
    display_banner()
    
    # Check dependencies early
    check_dependencies()  # This will check if Ollama is running and exit if not
    
    scheduler = None
    try:
        logger.info(f"Starting Jarvis in {mode} mode...")
        print(f"Starting Jarvis in {mode} mode...")
        
        if mode == "ui":
            # Set initialization flag and launch UI
            os.environ["JARVIS_INITIALIZED"] = "true"
            ui_path = os.path.join(PROJECT_ROOT, "web", "Jarvis_UI.py")
            subprocess.run([
                sys.executable, "-m", "streamlit", "run", ui_path,
                "--server.headless", "true", "--browser.serverAddress", "localhost"
            ])
        else:
            # Shell mode - start transcription
            print("Listening to your voice and processing in real-time...\n")
            scheduler = start_scheduler()
            transcribe_from_mic()
            
    except KeyboardInterrupt:
        # Handle keyboard interrupt specifically
        logger.info("Shutting down by keyboard interrupt...")
        print("\n🛑 Stopping by user request...")
        
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in {mode} mode: {e}")
        print(f"\nError: {str(e)}")
        
    finally:
        # Clean up resources in any case
        print("Stopping scheduler...")
        if scheduler:
            stop_scheduler()
            print("Scheduler stopped successfully")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis - AI Voice Assistant")
    parser.add_argument("--mode", "-m", choices=["shell", "ui"], default="shell",
                      help="Run mode: 'shell' for command line or 'ui' for web interface")
    run_jarvis(parser.parse_args().mode)
