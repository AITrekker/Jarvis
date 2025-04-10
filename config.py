import os
import platform
import whisper
import logging

#######################
# ENVIRONMENT SETTINGS
#######################

# Project paths
PROJECT_ROOT = os.environ.get('JARVIS_ROOT', os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = PROJECT_ROOT  # Adding BASE_DIR for backward compatibility
DATA_DIR = os.environ.get('JARVIS_DATA_DIR', os.path.join(PROJECT_ROOT, "data"))

# Get current system
SYSTEM = platform.system()

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

########################
# FILE SYSTEM SETTINGS
########################

# Transcript settings
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcripts")
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# Summary settings
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")
os.makedirs(SUMMARY_DIR, exist_ok=True)

# Logs
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

########################
# DATABASE SETTINGS
########################

# ChromaDB settings
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
CHROMA_DB_IMPL = "duckdb+parquet"

########################
# MODEL SETTINGS
########################

# Platform-specific configurations
PLATFORM_CONFIGS = {
    "Darwin": {  # macOS
        "whisper_model": "large-v3-turbo",
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
WHISPER_MODEL = whisper.load_model(MODEL_NAME)

# Ollama settings
OLLAMA_MODEL = config["ollama_model"]
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

########################
# API SETTINGS
########################

# API endpoints
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_EMBEDDINGS_URL = f"{OLLAMA_BASE_URL}/api/embeddings"

########################
# UI SETTINGS
########################

# UI defaults - move from Jarvis_UI_Pro.py
UI_PAGE_TITLE = "Jarvis Assistant"
UI_PAGE_ICON = "🤖"
UI_LAYOUT = "wide"
UI_SIDEBAR_STATE = "expanded"
UI_DEFAULT_MODELS = ["phi4", "llama3", "mistral", "codellama"]
UI_DEFAULT_MODEL = "phi4"

########################
# SEARCH SETTINGS
########################

# Default search parameters
SEARCH_DEFAULT_TOP_K = 5
SEARCH_MIN_RELEVANCE = 0.7  # Minimum relevance score (0-1)
SEARCH_HIGHLIGHT_THRESHOLD = 3  # Minimum characters for keyword highlighting

########################
# TIMING SETTINGS
########################

# Timing
TRANSCRIPT_AGGREGATION_MIN = 15  # How often to create new transcript files (minutes)
SUMMARY_INTERVAL_MIN = 15
SUMMARY_FILE_ROLLOVER_MIN = 60
CHUNK_DURATION = 10  # Audio chunk duration (seconds)

########################
# PROCESSING SETTINGS
########################

# Summary processing
SUMMARY_MAX_CHARS = 8000
USE_SUMMARY_CHUNKING = True

# LLM parameters
OLLAMA_TEMPERATURE = 0.7
OLLAMA_MAX_TOKENS = 1024

########################
# AUDIO SETTINGS
########################

# Audio config
SAMPLERATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "wav"

########################
# LOGGING SETTINGS
########################

# Logging configuration
LOG_LEVEL = logging.INFO  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL

# Initialize platform-specific logging
def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(LOG_DIR, "jarvis.log"))
        ]
    )
    return logging.getLogger(__name__)

# Create logger
logger = setup_logging()

# Print initialization info
logger.info(f"Running on {SYSTEM}")
logger.info(f"Loading Whisper model: {MODEL_NAME}")
logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
