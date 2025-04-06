# Jarvis - Voice Transcription and Summarization System

Jarvis is a real-time voice transcription and summarization system that listens to your microphone, transcribes speech using OpenAI Whisper, and periodically generates summaries using Ollama.

## Features

- Real-time transcription from microphone input
- Platform-specific configuration (Windows/Mac/Linux)
- Periodic summarization of transcribed content
- Persistent storage of transcripts and summaries

The system will:
- Check dependencies (FFmpeg, Ollama)
- Start listening to your microphone
- Save transcripts to JSON files
- Generate summaries every few minutes

## Requirements

- Python 3.11
- FFmpeg installed and in PATH
- Ollama running locally with the configured model

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Install FFmpeg from https://ffmpeg.org/download.html and add to PATH variable

## Usage

1. Run the application: `python main.py`

Start the application:

## Project Structure

- `mic_stream/`: Audio capture and transcription
- `storage/`: Data persistence and retrieval
- `summarizer/`: Text summarization logic
- `scheduler/`: Periodic task handling
- `tests/`: Unit tests
