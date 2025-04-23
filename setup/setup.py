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
        print("❌ FFmpeg is not installed or not in your PATH.")
        print("➡️  Please install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.")
        sys.exit(1)
    print("✅ FFmpeg is available")

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
            print(f"✅ Ollama server is running (version: {version})")
            return True
        else:
            print(f"❌ Ollama server returned status code {response.status_code}")
            return False
                
    except requests.exceptions.ConnectionError:
        print(f"❌ Ollama server connection refused")
        print("   This usually means Ollama is not running.")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Ollama server connection timed out")
        print("   The server might be overloaded or unresponsive.")
        return False
    except Exception as e:
        print(f"❌ Error checking Ollama server: {str(e)}")
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
            print("✅ Ollama API is fully functional")
            return True
        else:
            print(f"❌ Ollama API test returned status code {response.status_code}")
            print("   There might be an issue with the Ollama installation.")
            return False
                
    except requests.exceptions.ConnectionError:
        print("❌ Lost connection to Ollama server during API test")
        return False
    except requests.exceptions.Timeout:
        print("❌ Ollama API test timed out")
        print("   The server might be overloaded.")
        return False
    except Exception as e:
        print(f"❌ Error testing Ollama API: {str(e)}")
        return False

def check_ollama_models(required_models, debug=False):
    """Check if required Ollama models are installed."""
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Failed to get Ollama model list")
        return False
    
    # Parse output to get available models
    model_list = result.stdout.strip().split('\n')
    available_models = []
    
    # Skip header line and process model list
    for line in model_list[1:] if len(model_list) > 1 else []:
        parts = line.split()
        if parts:
            model_name = parts[0].lower()
            available_models.append(model_name)
    
    logger.debug(f"Available Ollama models: {available_models}")
    
    # Check for each required model
    missing_models = []
    for model in required_models:
        model_found = False
        model_lower = model.lower()
        for available in available_models:
            base_name = available.split(':')[0] if ':' in available else available
            required_base = model_lower.split(':')[0] if ':' in model_lower else model_lower
            if available == model_lower or base_name == required_base:
                print(f"✅ Found Ollama model: {available}")
                model_found = True
                break
        if not model_found:
            print(f"❌ Required Ollama model '{model}' is not installed.")
            missing_models.append(model)
    
    # Automatically pull missing models
    if missing_models:
        print("\n❌ Some required models are missing from your Ollama installation.")
        print("Attempting to pull missing models automatically...\n")
        for model in missing_models:
            print(f"Pulling model: {model} ...")
            pull_result = subprocess.run(["ollama", "pull", model])
            if pull_result.returncode == 0:
                print(f"✅ Successfully pulled {model}")
            else:
                print(f"❌ Could not pull {model}. Please install it manually: ollama pull {model}")
        print("\nAfter installing the models, restart the application if needed.")
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