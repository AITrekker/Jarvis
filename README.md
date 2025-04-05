# Jarvis - Voice Transcription and Summarization

A system for continuous voice transcription and summarization.

## Features

- Real-time audio transcription using Whisper
- Aggregation of transcripts by 15-minute intervals
- Robust error handling and testing

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `python main.py`

## Project Structure

- `mic_stream/`: Audio capture and transcription
- `storage/`: Data persistence and retrieval
- `summarizer/`: Text summarization logic
- `scheduler/`: Periodic task handling
- `tests/`: Unit tests
