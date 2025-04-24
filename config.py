import os
import platform
import whisper
import logging
import argparse
import sys

# Parse arguments for debug mode
parser = argparse.ArgumentParser(description="Jarvis AI Assistant")
parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
args, unknown = parser.parse_known_args()

# Debug setting
DEBUG_MODE = args.debug or False

#######################
# ENVIRONMENT SETTINGS
#######################

# Project paths
PROJECT_ROOT = os.environ.get('JARVIS_ROOT', os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = PROJECT_ROOT  # Adding BASE_DIR for backward compatibility
DATA_DIR = os.environ.get('JARVIS_DATA_DIR', os.path.join(PROJECT_ROOT, "data"))

# Get current system
SYSTEM = platform.system()

# Streamlit telemetry settings
ENV_VARS = {
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    "STREAMLIT_TELEMETRY": "false",
    "JARVIS_INITIALIZED": "false",  # Default to false, set to true in main.py
}

# Set environment variables when config is imported
for key, value in ENV_VARS.items():
    os.environ[key] = value

########################
# FILE SYSTEM SETTINGS
########################

# Create required directories
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcripts")
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")

# Create all directories at once
for directory in [DATA_DIR, TRANSCRIPT_DIR, SUMMARY_DIR, LOG_DIR, CHROMA_DIR]:
    os.makedirs(directory, exist_ok=True)

########################
# DATABASE SETTINGS
########################

# ChromaDB settings
CHROMA_DB_IMPL = "duckdb+parquet"

########################
# MODEL SETTINGS
########################

# Platform-specific configurations
PLATFORM_CONFIGS = {
    "Darwin": {  # macOS
        "whisper_model": "large-v3-turbo",
        "ollama_model": "mistral:instruct"
    },
    "Windows": {
        "whisper_model": "base.en",
        "ollama_model": "gemma:2b"
    },
    "Linux": {  # Default fallback
        "whisper_model": "tiny.en",
        "ollama_model": "mistral:instruct"
    }
}

# Use platform config or fall back to Linux config if system not recognized
config = PLATFORM_CONFIGS.get(SYSTEM, PLATFORM_CONFIGS["Linux"])

# Whisper model settings
MODEL_NAME = config["whisper_model"]
WHISPER_MODEL = whisper.load_model(MODEL_NAME)  # Direct loading (no lazy loading)

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

# Ollama API settings
OLLAMA_STREAM = False  # Whether to stream responses from Ollama

########################
# UI SETTINGS
########################

# UI defaults - move from Jarvis_UI_Pro.py
UI_PAGE_TITLE = "Jarvis Assistant"
UI_PAGE_ICON = "🤖"
UI_LAYOUT = "wide"
UI_SIDEBAR_STATE = "expanded"
#UI_DEFAULT_MODELS = ["phi4", "llama3", "mistral", "codellama"]
UI_DEFAULT_MODEL = OLLAMA_MODEL

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

# Initialize logging
# logging.basicConfig(
#     level=LOG_LEVEL,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler(os.path.join(LOG_DIR, "jarvis.log"))
#     ]
# )

# Create logger
import logging
logger = logging.getLogger(__name__)

# Print initialization info
logger.info(f"Running on {SYSTEM}")
logger.info(f"Using Ollama model: {OLLAMA_MODEL}")

# Ollama RAG system prompt
OLLAMA_RAG_SYSTEM_PROMPT = """You are Jarvis, a professional and helpful AI personal assistant with access to past conversation embeddings and summaries.
When responding to the user's query, prioritize exact matches and closely related content from the provided documents.
Explicitly reference specific information from the documents when appropriate.
Do not make up information. If the provided documents do not contain relevant information, clearly state that."""

# RAG prompt configuration
RAG_QUERY_PREFIX = "Query: "
RAG_CONTEXT_HEADER = "\n\nRelevant conversation history:\n"
RAG_DOCUMENT_HEADER = "\n--- Document {num} (Relevance: {relevance:.1f}%) ---\n"
RAG_DATE_FORMAT = "Date: {timestamp}\n"
RAG_SUMMARY_FORMAT = "Summary: {summary}\n"
RAG_FINAL_INSTRUCTION = "\nPlease provide a professional and helpful response using only the provided documents. Prioritize exact matches and explicitly reference relevant documents. If no relevant information is found, clearly state that."

# RAG relevance calculation
RAG_RELEVANCE_FACTOR = 100  # Multiply (1 - distance) by this factor
