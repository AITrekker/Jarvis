    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         ██╗  █████╗  ██████╗  ██╗   ██╗ ██╗ ███████╗       ║
    ║         ██║ ██╔══██╗ ██╔══██╗ ██║   ██║ ██║ ██╔════╝       ║
    ║         ██║ ███████║ ██████╔╝ ██║   ██║ ██║ ███████╗       ║
    ║         ██║ ██╔══██║ ██╔══██╗ ╚██╗ ██╔╝ ██║ ╚════██║       ║
    ║      █████║ ██║  ██║ ██║  ██║  ╚████╔╝  ██║ ███████║       ║
    ║      ╚════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝   ╚═══╝   ╚═╝ ╚══════╝       ║
    ║                                                            ║
    ║   Your AI assistant that listens, remembers, and recalls   ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝

# Jarvis - Your Personal AI Assistant

Jarvis is an advanced, locally-run AI assistant that transforms spoken conversations and text-based queries into a searchable, actionable knowledge base. By combining real-time transcription, a powerful tool-using framework, and a flexible web interface, Jarvis becomes your personal command center for information retrieval and task automation.

## Executive Summary

Jarvis addresses the critical challenge of capturing and retrieving valuable information from both verbal communications and external data sources. By continuously listening, transcribing, and summarizing conversations, and by providing a powerful tool integration for real-time information access (like web search), Jarvis ensures that no important detail is ever lost and that complex queries can be answered efficiently.

## Core Technology Stack

- **Audio Processing**: Real-time audio capture via PyAudio.
- **Speech Recognition**: High-accuracy transcription using OpenAI Whisper.
- **AI Models**: Local and private large language models (LLMs) served with Ollama.
- **Vector Database**: ChromaDB for efficient semantic search over conversation transcripts.
- **Embedding Generation**: `nomic-embed-text` for creating context-aware search embeddings.
- **Web Interface**: Interactive UI built with Gradio, providing a modern chat experience.
- **Tool Server**: A Model-Context-Protocol (MCP) compliant server built with Flask, enabling easy integration of new tools.

## Key Capabilities

- **Real-time Transcription**: Captures conversations with high accuracy.
- **Intelligent Summarization**: Automatically generates concise summaries of your conversations.
- **Semantic Search**: Understands the meaning behind your queries, not just keywords, allowing for natural language information retrieval from your conversation history.
- **Tool Integration**: A flexible framework for adding new capabilities. Comes with pre-built tools for:
    - **Web Search**: Find up-to-date information on any topic using DuckDuckGo.
    - **Weather**: Get the current weather forecast for any location.
    - **Time**: Get the current time for any location.
- **Interactive Chat UI**: A modern web interface for chatting with Jarvis, searching transcripts, and viewing conversation history.
- **Conversation Timeline**: Visualize your conversation history and manage individual entries.
- **Model Selection**: Dynamically switch between different Ollama models through the UI.
- **Cross-platform Compatibility**: Runs on Windows, macOS, and Linux.

## Technical Architecture

Jarvis employs a modular, microservice-inspired architecture:

-   **Main Application (`start_Jarvis.py`)**: The central entry point that can run the core listener or launch the web UI. It manages background processes for the other components.
-   **Gradio Web UI (`web/`)**: Provides the complete user interface, including the chat, conversation timeline, and model selector. It communicates with the LLM handler and the MCP tool server.
-   **MCP Tool Server (`mcp-server/`)**: A Flask-based server that exposes tools (like weather, time, and web search) over a simple HTTP API. It follows the Model-Context-Protocol, making it easy to add new tools.
-   **LLM Handler (`web/web_utils/llm_handler.py`)**: Centralizes all calls to the Ollama API, streamlining interaction with the language models.
-   **Tool Manager (`utils/tool_manager.py`)**: Discovers available tools and dynamically constructs the prompts needed for the LLM to decide which tool to use.
-   **Search Handler (`web/web_utils/search_handler.py`)**: Manages semantic search and RAG (Retrieval-Augmented Generation) over the ChromaDB vector store.
-   **Data Storage (`data/`)**: Contains the SQLite database for conversation metadata and the ChromaDB vector store for searchable transcript chunks.

## Technical Requirements

- Python 3.11
- FFmpeg for audio processing
- Ollama with your desired models (e.g., `phi3`, `llama3`) and the `nomic-embed-text` model for embeddings.
- A C++ compiler (required by `ChromaDB`). On Windows, you'll need Microsoft C++ Build Tools.
- 8GB+ RAM recommended for optimal performance.

## Getting Started

1.  **Clone the Repository**: `git clone https://github.com/AITrekker/Jarvis`
2.  **Install Dependencies**:
    - Ensure you have [Ollama](https://ollama.com) installed and have downloaded the models you wish to use (e.g., `ollama pull phi3`, `ollama pull nomic-embed-text`).
    - Install FFmpeg for your operating system.
    - Install the required Python packages:
      ```bash
      pip install -r requirements.txt
      ```
3.  **Run the Application**:
    - The application now uses a Gradio web interface and can optionally run a background server for tools.
    - To launch the full application with the UI and the MCP tool server, run:
      ```bash
      python start_Jarvis.py --mode ui --mcp
      ```
    - The UI will be available at `http://127.0.0.1:7860`.

## Project Structure

- `data/`: Stores transcripts, summaries, and the ChromaDB vector database.
- `logs/`: Contains detailed system logs.
- `mcp-server/`: The Model-Context-Protocol tool server.
  - `tools/`: Individual tool packages, each with its own `tool.py` and `schema.json`.
- `utils/`: Core utilities, including the `ToolManager`.
- `web/`: The Gradio web interface.
  - `components/`: Individual Gradio components (chat, timeline, etc.).
  - `web_utils/`: Backend utilities for the web interface (search, LLM calls).
- `start_Jarvis.py`: The main entry point for the application.
- `requirements.txt`: The list of Python dependencies.