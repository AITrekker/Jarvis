from mic_stream.recorder import transcribe_from_mic
from scheduler.periodic_tasks import start_scheduler, stop_scheduler
import config  # Import config to ensure platform detection runs
import logging

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import shutil
import sys
import requests
import json
import time

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("❌ FFmpeg is not installed or not in your PATH.")
        print("➡️  Please install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.")
        sys.exit(1)

def check_ollama_models():
    """Check if all required Ollama models are available and pull them if needed."""
    # List of all models required by the application
    required_models = [
        config.OLLAMA_MODEL,           # Main model for generation
        config.OLLAMA_EMBEDDING_MODEL  # Model for embeddings
    ]
    
    logger.info(f"Checking if required Ollama models are available locally...")
    
    for model_name in required_models:
        model_found = False
        max_retries = 3
        
        logger.info(f"Checking for model: {model_name}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    for model in models:
                        model_tag = model.get("name", "")
                        # Compare base model name (without tags)
                        if model_tag.split(":")[0] == model_name:
                            model_found = True
                            logger.info(f"✅ Found Ollama model: {model_tag}")
                            break
                
                if model_found:
                    break  # Model found, exit loop
                
                if attempt < max_retries - 1:
                    logger.info(f"⚠️ Ollama model '{model_name}' not found locally. Attempting to pull it...")
                    pull_response = requests.post(
                        "http://localhost:11434/api/pull",
                        json={"name": model_name},
                        stream=True
                    )
                    if pull_response.status_code == 200:
                        for line in pull_response.iter_lines():
                            if line:
                                status = json.loads(line.decode('utf-8'))
                                if 'error' in status:
                                    logger.warning(f"⚠️ Error pulling model: {status['error']}")
                                    break
                        else:
                            logger.info(f"✅ Successfully pulled model: {model_name}")
                            model_found = True
                            break
                    else:
                        logger.warning(f"⚠️ Failed to pull model. Retrying in 2 seconds...")
                        time.sleep(2)
            
            except requests.exceptions.ConnectionError:
                logger.error(f"❌ Ollama server not running. Attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    logger.info("Waiting 2 seconds before retrying...")
                    time.sleep(2)
        
        if not model_found:
            logger.error(f"❌ Could not find or pull Ollama model '{model_name}'.")
            logger.error("➡️  Please ensure Ollama is running and install the model manually:")
            logger.error(f"    ollama pull {model_name}")
            sys.exit(1)
    
    logger.info("✅ All required Ollama models are available")

if __name__ == "__main__":
    print("Starting Jarvis voice transcription system...")
    logger.info("Starting Jarvis voice transcription system...")
    
    check_ffmpeg()
    check_ollama_models()  
    scheduler = start_scheduler()
    try:
        transcribe_from_mic()
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        stop_scheduler()
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        stop_scheduler()
