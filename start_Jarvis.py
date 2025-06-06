"""
Jarvis Application Launcher

This script serves as the main entry point for starting the Jarvis application,
initializing all required components and services.

Role in the system:
- Performs dependency checks and validation
- Initializes logging and configuration
- Starts required background services (Ollama, ChromaDB)
- Launches the recorder and transcription system
- Initializes and starts the web interface
- Handles graceful shutdown on exit

To run the Jarvis application, users should execute this script after completing
the initial setup process with setup_Jarvis.py.
"""

import argparse
import subprocess
import sys
import os
import logging
import threading
import time
import itertools

def ensure_venv():
    """Ensure the script is running inside a virtual environment."""
    # More reliable venv detection for all platforms including macOS
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        os.environ.get('VIRTUAL_ENV') is not None
    )
    
    if not in_venv:
        if os.name == "nt":
            activate_cmd = r".venv\Scripts\activate.bat"
        else:
            activate_cmd = "source .venv/bin/activate"
        print(
            f"\n🛑 JARVIS likes to run inside a virtual environment!\n"
            f"\nPlease activate it first:\n    {activate_cmd}\n"
            f"\nThen run this script again.\n"
        )
        sys.exit(1)

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_banner():
    """Display ASCII art banner."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         ██╗  █████╗  ██████╗  ██╗   ██╗ ██╗ ███████╗       ║
    ║         ██║ ██╔══██╗ ██╔══██╗ ██║   ██║ ██║ ██╔════╝       ║
    ║         ██║ ███████║ ██████╔╝ ██║   ██║ ██║ ███████╗       ║
    ║         ██║ ██╔══██║ ██╔══██╗ ╚██╗ ██╔╝ ██║ ╚════██║       ║
    ║      █████║ ██║  ██║ ██║  ██║  ╚████╔╝  ██║ ███████║       ║
    ║      ╚════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝   ╚═══╝   ╚═╝ ╚══════╝       ║
    ║                                                            ║
    ║   Your AI assistant that listens, remembers, and recalls   ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)

def loading_animation(stop_event):
    """Display a simple loading animation until stop_event is set."""
    spinners = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while not stop_event.is_set():
        spinner = spinners[i % len(spinners)]
        sys.stdout.write(f"\r  {spinner} Initializing Jarvis...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * 30 + "\r")  # Clear the line
    sys.stdout.flush()

def configure_logging(debug=False):
    """Configure logging level based on debug flag."""
    import logging
    from config import LOG_DIR

    # Clear existing handlers to allow reconfiguration
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Use UTF-8 encoding for all handlers
    log_file_handler = logging.FileHandler(os.path.join(LOG_DIR, "jarvis.log"), encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            stream_handler,
            log_file_handler
        ]
    )
    logger = logging.getLogger(__name__)
    logger.debug("Debug mode enabled: Verbose logging activated." if debug else "Logging set to INFO level.")

def start_mcp_server(debug=False):
    """Start the MCP server as a background process."""
    from config import PROJECT_ROOT, logger
    mcp_server_path = os.path.join(PROJECT_ROOT, "mcp-server", "server.py")
    
    if not os.path.exists(mcp_server_path):
        logger.error("MCP server script not found at: %s", mcp_server_path)
        return None

    try:
        # Start the MCP server in a non-blocking way
        mcp_process = subprocess.Popen([sys.executable, mcp_server_path])
        logger.info("MCP server started successfully.")
        return mcp_process
    except Exception as e:
        logger.error("Failed to start MCP server: %s", e)
        return None

def run_jarvis(mode="shell", debug=False, start_mcp=False):
    """Main entry point for Jarvis."""
    # Import heavy modules after banner and logging configuration
    from config import PROJECT_ROOT, logger
    from utils.periodic_tasks import start_scheduler, stop_scheduler
    from utils.recorder import transcribe_from_mic
    from setup.setup import check_dependencies

    logger.debug("Checking dependencies...")
    check_dependencies(debug)  # Pass debug flag to dependency checker

    mcp_process = None
    if start_mcp:
        logger.debug("Starting MCP server as requested...")
        mcp_process = start_mcp_server(debug)

    scheduler = None
    try:
        print(f"Starting Jarvis in {mode} mode...")

        if mode == "gradio":
            logger.debug("Launching Gradio UI mode...")
            os.environ["JARVIS_INITIALIZED"] = "true"
            ui_path = os.path.join(PROJECT_ROOT, "web", "Gradio_UI.py")
            subprocess.run([sys.executable, ui_path])
        else:
            logger.debug("Launching shell mode transcription...")
            scheduler = start_scheduler()
            transcribe_from_mic()

    except KeyboardInterrupt:
        logger.info("Shutting down by keyboard interrupt...")
        print("\n🛑 Stopping by user request...")

    except Exception as e:
        logger.error(f"Error in {mode} mode: {e}")
        print(f"\nError: {str(e)}")

    finally:
        logger.debug("Cleaning up resources...")
        if scheduler:
            stop_scheduler()
            logger.debug("Scheduler stopped successfully")
        
        if mcp_process:
            logger.debug("Stopping MCP server...")
            mcp_process.terminate()
            mcp_process.wait()
            logger.debug("MCP server stopped.")

        logger.debug("Shutdown complete.")

if __name__ == "__main__":
    # On Windows, ensure console supports UTF-8 for emoji rendering
    if sys.platform == "win32":
        # This helps render emojis and other Unicode characters correctly in the console
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (TypeError, AttributeError):
            # In environments where reconfigure is not available (like some IDEs' embedded terminals),
            # this will fail. We'll proceed without it, accepting potential display issues.
            pass

    # Clear screen before displaying banner
    clear_screen()

    # Display banner immediately upon execution
    display_banner()

    # Ensure running inside virtual environment
    ensure_venv()
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Jarvis - AI Voice Assistant")
    parser.add_argument("--mode", "-m", choices=["shell", "gradio"], default="shell",
                        help="Run mode: 'shell' for command line, or 'gradio' for Gradio interface")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Enable debug mode with verbose logging")
    parser.add_argument("--mcp", action="store_true",
                        help="Enable the MCP server for tool usage")
    args = parser.parse_args()

    # Start loading animation in a separate thread
    stop_loading = threading.Event()
    loading_thread = threading.Thread(target=loading_animation, args=(stop_loading,))
    loading_thread.daemon = True
    loading_thread.start()

    try:
        # Configure logging (this may take some time)
        configure_logging(args.debug)

        # Stop the loading animation
        stop_loading.set()
        loading_thread.join()

        # Run Jarvis
        run_jarvis(mode=args.mode, debug=args.debug, start_mcp=args.mcp)
    except Exception as e:
        # In case of error, make sure we stop the loading animation
        stop_loading.set()
        raise e
