from mic_stream.recorder import transcribe_from_mic
from scheduler.periodic_tasks import start_scheduler
import config  # Import config to ensure platform detection runs

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

def check_ollama():
    print(f"Checking if Ollama model '{config.OLLAMA_MODEL}' is available locally...")
    model_found = False
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    model_name = model.get("name", "")
                    # Corrected check: split model name at ":" and compare first part
                    if model_name.split(":")[0] == config.OLLAMA_MODEL:
                        model_found = True
                        print(f"✅ Found Ollama model: {model_name}")
                        break

            if model_found:
                break  # Model found, exit loop

            if attempt < max_retries - 1:
                print(f"⚠️ Ollama model '{config.OLLAMA_MODEL}' not found locally. Attempting to pull it...")
                pull_response = requests.post(
                    "http://localhost:11434/api/pull",
                    json={"name": config.OLLAMA_MODEL},
                    stream=True
                )
                if pull_response.status_code == 200:
                    for line in pull_response.iter_lines():
                        if line:
                            status = json.loads(line.decode('utf-8'))
                            if 'error' in status:
                                print(f"⚠️ Error pulling model: {status['error']}")
                                break
                    else:
                        print(f"✅ Successfully pulled model: {config.OLLAMA_MODEL}")
                        model_found = True
                        break
                else:
                    print(f"⚠️ Failed to pull model. Retrying in 2 seconds...")
                    time.sleep(2)

        except requests.exceptions.ConnectionError:
            print(f"❌ Ollama server not running. Attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print("Waiting 2 seconds before retrying...")
                time.sleep(2)

    if not model_found:
        print(f"❌ Could not find or pull Ollama model '{config.OLLAMA_MODEL}'.")
        print("➡️  Please ensure Ollama is running and install the model manually:")
        print(f"    ollama pull {config.OLLAMA_MODEL}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Jarvis voice transcription system...")
    
    check_ffmpeg()
    check_ollama()
    start_scheduler()
    try:
        transcribe_from_mic()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Error during transcription: {e}")
