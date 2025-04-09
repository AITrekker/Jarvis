import os
import platform
import whisper
import logging

# Project paths
PROJECT_ROOT = os.environ.get('JARVIS_ROOT', os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = PROJECT_ROOT  # Adding BASE_DIR for backward compatibility
DATA_DIR = os.environ.get('JARVIS_DATA_DIR', os.path.join(PROJECT_ROOT, "data"))

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Transcript settings
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcripts")
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# Summary settings
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")
os.makedirs(SUMMARY_DIR, exist_ok=True)
SUMMARY_INTERVAL_MIN = 15
SUMMARY_FILE_ROLLOVER_MIN = 60
SUMMARY_MAX_CHARS = 8000
USE_SUMMARY_CHUNKING = True

# ChromaDB settings
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
CHROMA_DB_IMPL = "duckdb+parquet"

# API endpoints
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_EMBEDDINGS_URL = f"{OLLAMA_BASE_URL}/api/embeddings"

# Models
OLLAMA_MODEL = "phi4"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

# Get current system
SYSTEM = platform.system()
print(f"Running on {SYSTEM}")

# Logging configuration
LOG_LEVEL = logging.INFO  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

# Timing
TRANSCRIPT_AGGREGATION_MIN = 15  # How often to create new transcript files (minutes)
CHUNK_DURATION = 10              # Audio chunk duration (seconds)

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
OLLAMA_MODEL = config["ollama_model"]
print(f"Using Ollama model: {OLLAMA_MODEL}")
