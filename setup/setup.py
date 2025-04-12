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

def is_ollama_running():
    """
    Check if Ollama server is running and accessible.
    Only tests the basic version endpoint to confirm the server is up.
    """
    base_url = "http://localhost:11434"
    
    logger.info("Checking if Ollama server is running...")
    
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

def check_ollama_api():
    """Check if the Ollama API is functional for generating text."""
    base_url = "http://localhost:11434"
    
    logger.info("Verifying Ollama API functionality...")
    
    try:
        # Test a minimal generate request
        response = requests.post(
            f"{base_url}/api/generate", 
            json={"model": "list", "prompt": ""}, 
            timeout=5.0
        )
        
        # Status code of 404 here usually means the server is running but "list" isn't available
        if response.status_code == 404:
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

def check_ollama_models():
    """Check if all required Ollama models are available locally."""
    # First check if Ollama is running
    if not is_ollama_running():
        logger.error("➡️  Please start the Ollama server before running this application.")
        logger.error("   You can download Ollama from: https://ollama.com/download")
        sys.exit(1)
    
    # Then verify the API works (but don't exit if the 'list' model isn't found)
    api_ok = check_ollama_api()
    if not api_ok:
        logger.error("➡️  There appears to be an issue with your Ollama installation.")
        logger.error("   Please check that Ollama is properly installed and running.")
        sys.exit(1)
    
    # List of all models required by the application
    required_models = [
        config.OLLAMA_MODEL,           # Main model for generation
        config.OLLAMA_EMBEDDING_MODEL  # Model for embeddings
    ]
    
    logger.info(f"Checking if required Ollama models are available locally...")
    missing_models = []
    
    # Check for each required model
    for model_name in required_models:
        logger.info(f"Checking for model: {model_name}")
        try:
            # List all available models
            response = requests.get(
                "http://localhost:11434/api/tags", 
                timeout=5.0
            )
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_found = False
                
                for model in models:
                    model_tag = model.get("name", "")
                    # Compare base model name (without tags)
                    if model_tag.split(":")[0] == model_name:
                        model_found = True
                        logger.info(f"✅ Found Ollama model: {model_tag}")
                        break
                
                if not model_found:
                    missing_models.append(model_name)
                    logger.error(f"❌ Required Ollama model '{model_name}' is not installed.")
            else:
                logger.error(f"❌ Error checking models, API returned {response.status_code}")
                missing_models.append(model_name)
        
        except Exception as e:
            logger.error(f"❌ Error checking for model '{model_name}': {str(e)}")
            missing_models.append(model_name)
    
    # If any models are missing, provide instructions and exit
    if missing_models:
        logger.error("\n❌ Some required models are missing from your Ollama installation.")
        logger.error("Please install the following models manually using these commands:\n")
        
        for model in missing_models:
            logger.error(f"    ollama pull {model}")
        
        logger.error("\nAfter installing the models, restart the application.")
        sys.exit(1)
    
    logger.info("✅ All required Ollama models are available")

def check_dependencies():
    """Run all dependency checks."""
    check_ffmpeg()
    check_ollama_models()