import os
import platform
import whisper
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Get current system
SYSTEM = platform.system()
print(f"Running on {SYSTEM}")

# Paths
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "data", "transcripts")
SUMMARY_DIR = os.path.join(BASE_DIR, "data", "summaries")

# Logging configuration
LOG_LEVEL = logging.INFO  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Timing
TRANSCRIPT_AGGREGATION_MIN = 15  # How often to create new transcript files (minutes)
SUMMARY_INTERVAL_MIN = 15        # How often to run summarization (minutes)
SUMMARY_FILE_ROLLOVER_MIN = 60   # How often to create new summary files (minutes)
CHUNK_DURATION = 10              # Audio chunk duration (seconds)

# Summary settings
SUMMARY_MAX_CHARS = 8000         # Max characters per summary prompt (approximate token limit)
USE_SUMMARY_CHUNKING = True      # Set to False to disable chunking entirely

# Audio config
SAMPLERATE = 16000
CHANNELS = 1

# Platform-specific configurations
PLATFORM_CONFIGS = {
    "Darwin": {  # macOS
        "whisper_model": "large-v3-turbo", #medium.en earlier
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
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_EMBEDDINGS_URL = f"{OLLAMA_BASE_URL}/api/embeddings"
OLLAMA_MODEL = config["ollama_model"]
print(f"Using Ollama model: {OLLAMA_MODEL}")

# Ollama embedding model
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
