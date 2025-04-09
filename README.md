# Jarvis - Voice Transcription and Summarization System

Jarvis is a real-time voice transcription and summarization system that listens to your microphone, transcribes speech using OpenAI Whisper, and periodically generates summaries using Ollama.

## Features

### Currently Implemented
- **Real-time transcription**: Captures audio from the microphone and transcribes it using OpenAI Whisper.
- **Platform-specific configuration**: Works seamlessly on Windows, Mac, and Linux.
- **Periodic summarization**: Generates summaries of transcribed content every few minutes using Ollama.
- **Persistent storage**: Saves transcripts and summaries as JSON files for later retrieval.
- **Dynamic logging**: Centralized logging with adjustable log levels for debugging and monitoring.
- **Dependency checks**: Ensures FFmpeg and Ollama are installed and running before starting the application.
- **Unit tests**: Comprehensive test suite to ensure code stability and correctness.

### Coming Soon
- **Speaker identification**: Detect and label different speakers in the transcription.
- **Semantic search**: Search transcripts and summaries using vector embeddings for context-aware retrieval.
- **Web interface**: A user-friendly web dashboard for managing transcripts and summaries.
- **Custom summarization intervals**: Allow users to configure the frequency of summary generation.
- **Cloud storage integration**: Option to save transcripts and summaries to cloud services like AWS S3 or Google Drive.
- **Multi-language support**: Extend transcription and summarization to support multiple languages.

## Requirements

- Python 3.11
- FFmpeg installed and in PATH
- Ollama running locally with the configured model

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH variable.
3. Ensure Ollama is running locally and the required models (`phi4`, `nomic-embed-text`) are installed.

## Usage

1. Run the application:
   ```bash
   python main.py

2. The system will:
- Check dependencies (FFmpeg, Ollama)
- Start listening to your microphone
- Save transcripts to JSON files
- Generate summaries every few minutes

## Project Structure

- mic_stream/: Audio capture and transcription
- storage/: Data persistence and retrieval
- summarizer/: Text summarization logic
- scheduler/: Periodic task handling
- logger/: Centralized logging configuration
- tests/: Unit tests