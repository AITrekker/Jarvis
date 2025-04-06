import os
import platform
import whisper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Get current system
SYSTEM = platform.system()
print(f"Running on {SYSTEM}")

# Paths
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "data", "transcripts")
SUMMARY_DIR = os.path.join(BASE_DIR, "data", "summaries")

# Timing
TRANSCRIPT_AGGREGATION_MIN = 5  # How often to create new transcript files (minutes)
SUMMARY_INTERVAL_MIN = 5        # How often to run summarization (minutes)
CHUNK_DURATION = 10             # Audio chunk duration (seconds)

# Audio config
SAMPLERATE = 16000
CHANNELS = 1

# Platform-specific configurations
PLATFORM_CONFIGS = {
    "Darwin": {  # macOS
        "whisper_model": "medium.en",
        "ollama_model": "phi4",
    },
    "Windows": {
        "whisper_model": "base.en",
        "ollama_model": "llama3.2",
    },
    "Linux": {  # Default fallback
        "whisper_model": "tiny.en",
        "ollama_model": "llama3.2",
    }
}

# Use platform config or fall back to Linux config if system not recognized
config = PLATFORM_CONFIGS.get(SYSTEM, PLATFORM_CONFIGS["Linux"])

# Whisper config
MODEL_NAME = config["whisper_model"]
print(f"Loading Whisper model: {MODEL_NAME}")
WHISPER_MODEL = whisper.load_model(MODEL_NAME)

# Ollama settings
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = config["ollama_model"]
print(f"Using Ollama model: {OLLAMA_MODEL}")
