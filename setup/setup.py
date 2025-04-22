import shutil
import sys
import requests
import json
import time
import logging
from setup.logger import logger 
import config
import subprocess

def check_ffmpeg(debug=False):
    """Check if FFmpeg is installed and available in PATH."""
    if debug:
        logger.debug("Running FFmpeg check with debug enabled")
    
    if not shutil.which("ffmpeg"):
        logger.error("❌ FFmpeg is not installed or not in your PATH.")
        logger.error("➡️  Please install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.")
        sys.exit(1)
    logger.info("✅ FFmpeg is available")

def is_ollama_running(debug=False):
    """
    Check if Ollama server is running and accessible.
    Only tests the basic version endpoint to confirm the server is up.
    """
    base_url = "http://localhost:11434"
    
    if debug:
        logger.debug("Checking Ollama server connection with debug enabled")
        
    try:
        # Only check the version endpoint as a basic connectivity check
        response = requests.get(f"{base_url}/api/version", timeout=5.0)
        
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            logger.info(f"✅ Ollama server is running (version: {version})")
            return True
        else:
            logger.error(f"❌ Ollama server returned status code {response.status_code}")
            return False
                
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Ollama server connection refused")
        logger.error("   This usually means Ollama is not running.")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"❌ Ollama server connection timed out")
        logger.error("   The server might be overloaded or unresponsive.")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking Ollama server: {str(e)}")
        return False

def check_ollama_api(debug=False):
    """Check if the Ollama API is functional for generating text."""
    base_url = "http://localhost:11434"
    
    if debug:
        logger.debug("Testing Ollama API")
    
    try:
        # Test a minimal generate request
        response = requests.post(
            f"{base_url}/api/generate", 
            json={"model": "list", "prompt": ""}, 
            timeout=5.0
        )
        
        # Status code of 404 here usually means the server is running but "list" isn't available
        if response.status_code == 404:
            if debug:
                logger.warning("⚠️ Ollama API is accessible but the 'list' model isn't available.")
                logger.warning("   This is normal and we'll continue checking for the required models.")
            return True
        elif response.status_code == 200:
            logger.info("✅ Ollama API is fully functional")
            return True
        else:
            logger.error(f"❌ Ollama API test returned status code {response.status_code}")
            logger.error("   There might be an issue with the Ollama installation.")
            return False
                
    except requests.exceptions.ConnectionError:
        logger.error("❌ Lost connection to Ollama server during API test")
        return False
    except requests.exceptions.Timeout:
        logger.error("❌ Ollama API test timed out")
        logger.error("   The server might be overloaded.")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing Ollama API: {str(e)}")
        return False

def check_ollama_models(required_models, debug=False):
    """Check if required Ollama models are installed."""
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error("❌ Failed to get Ollama model list")
        return False
    
    # Parse output to get available models
    model_list = result.stdout.strip().split('\n')
    available_models = []
    
    # Skip header line and process model list
    for line in model_list[1:] if len(model_list) > 1 else []:
        # The model format is typically: NAME ID SIZE MODIFIED
        parts = line.split()
        if parts:  # Ensure there's at least one part
            model_name = parts[0].lower()  # Get just the name part
            available_models.append(model_name)
    
    logger.debug(f"Available Ollama models: {available_models}")
    
    # Check for each required model
    missing_models = []
    for model in required_models:
        model_found = False
        model_lower = model.lower()
        
        # Check for exact match or match with tag variation
        for available in available_models:
            # Strip version tags for comparison (e.g., phi3:latest -> phi3)
            base_name = available.split(':')[0] if ':' in available else available
            required_base = model_lower.split(':')[0] if ':' in model_lower else model_lower
            
            if available == model_lower or base_name == required_base:
                logger.info(f"✅ Found Ollama model: {available}")
                model_found = True
                break
                
        if not model_found:
            logger.error(f"❌ Required Ollama model '{model}' is not installed.")
            missing_models.append(model)
    
    if missing_models:
        logger.error("\n❌ Some required models are missing from your Ollama installation.")
        logger.error("Please install the following models manually using these commands:\n")
        for model in missing_models:
            logger.error(f"    ollama pull {model}")
        logger.error("\nAfter installing the models, restart the application.")
        return False
    
    return True

def check_dependencies(debug=False):
    """Run all dependency checks."""
    if debug:
        logger.debug("Running dependency checks with debug mode enabled")
    
    check_ffmpeg(debug)
    required_models = [
        config.OLLAMA_MODEL,           # Main model for generation
        config.OLLAMA_EMBEDDING_MODEL  # Model for embeddings
    ]
    check_ollama_models(required_models, debug)