import os
import whisper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "data", "transcripts")
SUMMARY_DIR = os.path.join(BASE_DIR, "data", "summaries")

# Timing
SUMMARY_INTERVAL_MIN = 15
CHUNK_DURATION = 10  # in seconds

# Audio config
SAMPLERATE = 16000
CHANNELS = 1

# Whisper config
MODEL_NAME = "medium.en"
WHISPER_MODEL = whisper.load_model(MODEL_NAME)
