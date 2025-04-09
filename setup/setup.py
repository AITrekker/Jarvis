import shutil
import sys
import requests
import json
import time
from setup.logger import logger 
import config

def check_ffmpeg():
    """Check if FFmpeg is installed and available in PATH."""
    if not shutil.which("ffmpeg"):
        logger.error("❌ FFmpeg is not installed or not in your PATH.")
        logger.error("➡️  Please install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.")
        sys.exit(1)
    logger.info("✅ FFmpeg is available")

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

def check_dependencies():
    """Run all dependency checks."""
    check_ffmpeg()
    check_ollama_models()