# Jarvis - AI-Powered Voice Intelligence Platform

Jarvis is an advanced voice intelligence system that transforms spoken conversations into searchable, actionable knowledge. By combining real-time transcription, AI-powered summarization, and semantic search capabilities, Jarvis creates a comprehensive memory system for all your important conversations.

## Executive Summary

Jarvis addresses the critical challenge of capturing and retrieving valuable information from verbal communications. By continuously listening, transcribing, summarizing, and indexing conversations, Jarvis ensures that no important detail is ever lost and that information can be retrieved using natural language queries.

## Core Technology Stack

- **Audio Processing**: Real-time audio capture and processing using platform-optimized libraries
- **Speech Recognition**: High-accuracy transcription using OpenAI Whisper
- **AI Summarization**: Local LLM-powered summarization using Ollama models (phi4)
- **Vector Database**: ChromaDB for semantic search capabilities
- **Embedding Generation**: Neural embeddings for context-aware search (nomic-embed-text)
- **Web Interface**: Interactive UI built with Streamlit for intuitive user experience

## Key Capabilities

### Production-Ready Features

- **Real-time transcription**: Enterprise-grade speech-to-text using OpenAI Whisper, capturing conversations with high accuracy across various accents and technical terminology.

- **Intelligent Summarization**: Automated generation of concise, contextual summaries at configurable intervals using locally-hosted LLM technology, ensuring data privacy and security.

- **Semantic Search Engine**: Vector-based search technology that understands the meaning behind your queries, not just keywords, allowing for natural language information retrieval.

- **Topic Explorer**: Interactive exploration of conversation themes with AI-enhanced analysis of related discussions across time periods.

- **Cross-platform Compatibility**: Seamless operation across Windows, macOS, and Linux environments through platform-specific optimizations.

- **Robust Data Management**: Structured storage of transcripts and summaries with comprehensive metadata for advanced filtering and retrieval.

- **Enterprise Logging**: Detailed activity logs with configurable verbosity for system monitoring and compliance requirements.

- **Automated Testing**: Comprehensive test suite ensuring reliability and stability of all core components.

### Technical Architecture

Jarvis employs a modular architecture with clear separation of concerns:

- **Audio Capture Module**: Platform-optimized microphone streaming with configurable audio parameters
- **Transcription Engine**: API integration with Whisper models for high-accuracy speech recognition
- **Summarization Pipeline**: Temporal transcript aggregation and LLM-based summarization
- **Vector Database**: ChromaDB integration for embedding storage and similarity search
- **Web Dashboard**: Streamlit-based UI for intuitive interaction with the system
- **Scheduled Processing**: Background task management for periodic summarization

## Business Impact

- **Knowledge Retention**: Capture critical information from meetings, presentations, and conversations
- **Time Savings**: Quickly retrieve information without reviewing lengthy recordings or notes
- **Enhanced Decision Making**: Access comprehensive conversation history to inform strategic decisions
- **Improved Collaboration**: Share conversation insights across teams and departments
- **Compliance Support**: Maintain searchable records of important discussions for regulatory purposes

## Development Roadmap

- **Speaker Identification**: Advanced diarization to distinguish between speakers in multi-person conversations
- **Enhanced RAG Integration**: Deeper integration of retrieved context for more accurate question answering
- **Enterprise Authentication**: SSO integration and role-based access control
- **Cloud Deployment Options**: Scalable deployment configurations for AWS, Azure, and GCP
- **Mobile Companion App**: Remote access to transcripts and summaries via mobile interfaces
- **Integration APIs**: Connect with CRM, project management, and communication platforms

## Technical Requirements

- Python 3.11+
- FFmpeg for audio processing
- Ollama with phi4 and nomic-embed-text models
- ChromaDB for vector storage
- 8GB+ RAM recommended for optimal performance

## Getting Started

1. Install Python 3.11 from the `binaries` folder
2. Install Ollama from [https://ollama.com](https://ollama.com)
3. Run the setup script: `python setup_Jarvis.py` (Note: This can take a significant amount of time, please be patient)
4. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`
5. Launch the application:
   - For command line interface: `python start_Jarvis.py`
   - For web interface: `python start_Jarvis.py --mode ui`

## Project Structure

- `storage/`: Data persistence layer with file and vector database handlers
- `search/`: Semantic search engine with RAG capabilities
- `utils/`: Core utilities including summarization and periodic task management  
- `web/`: Interactive web interface components
- `tests/`: Comprehensive test suite for all major components
- `logs/`: System logs with configurable retention policies
- `data/`: Storage for transcripts, summaries, and vector databases