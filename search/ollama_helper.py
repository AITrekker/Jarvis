"""
Ollama LLM Integration Module

This module provides integration with Ollama for large language model operations,
particularly focused on Retrieval-Augmented Generation (RAG) functionality.

Role in the system:
- Provides direct interface to the Ollama API
- Formats prompts for RAG operations
- Processes search results to enhance them with LLM-generated responses
- Handles system and user prompts for optimal context utilization

Used primarily by search_engine.py for enhanced search results.
"""

import json
import requests
import logging
import sys
import os
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import config
from config import (
    OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE, OLLAMA_MAX_TOKENS,
    OLLAMA_RAG_SYSTEM_PROMPT, OLLAMA_STREAM, logger,
    RAG_QUERY_PREFIX, RAG_CONTEXT_HEADER, RAG_DOCUMENT_HEADER,
    RAG_DATE_FORMAT, RAG_SUMMARY_FORMAT, RAG_FINAL_INSTRUCTION,
    RAG_RELEVANCE_FACTOR
)

def query_ollama(system_prompt, user_prompt, model=OLLAMA_MODEL, temperature=OLLAMA_TEMPERATURE, max_tokens=OLLAMA_MAX_TOKENS):
    """
    Query the Ollama API with RAG context.
    
    Args:
        system_prompt: The system prompt to set context
        user_prompt: The user query with RAG content
        model: Ollama model to use
        temperature: Sampling temperature (higher = more creative)
        max_tokens: Maximum tokens to generate
        
    Returns:
        Generated response from Ollama
    """
    try:
        prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": OLLAMA_STREAM,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        logger.info(f"Querying Ollama with model: {model}")
        response = requests.post(OLLAMA_URL, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result["response"]
        else:
            logger.error(f"Ollama API error: {response.status_code}, {response.text}")
            return f"Error querying Ollama: {response.status_code}"
    
    except Exception as e:
        logger.error(f"Exception when calling Ollama API: {str(e)}")
        return f"Error: {str(e)}"

def rag_search(query: str, results: List[Dict[str, Any]], model: str = OLLAMA_MODEL) -> str:
    """
    Perform RAG search using Ollama.
    
    Args:
        query: User's query
        results: Normalized search results
        model: Model to use for RAG (defaults to OLLAMA_MODEL from config)
        
    Returns:
        Generated RAG response
    """
    # Extract content from results and ensure we have valid content
    documents = []
    for result in results:
        # Get content from result, with multiple fallbacks
        content = None
        
        # Try the standard 'content' field first
        if "content" in result and result["content"]:
            content = result["content"]
        # Fall back to metadata.summary
        elif "metadata" in result and result["metadata"] and "summary" in result["metadata"]:
            content = result["metadata"]["summary"]
        # Fall back to document field
        elif "document" in result:
            content = result["document"]
        
        if content:
            documents.append(content)
    
    # If no valid documents found, return error message
    if not documents:
        return "I couldn't find any relevant information to answer your question."
    
    # Prepare system prompt with context
    context = "\n\n".join(f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents))
    system_prompt = f"""You are Jarvis, an AI assistant providing answers based on specific conversation transcripts.
Answer the user's question based ONLY on the information in these conversation transcripts.
If the transcripts don't contain relevant information, say so clearly.

Here are the relevant conversation transcripts:

{context}"""

    # Use the existing query_ollama function instead of the undefined generate_response
    response = query_ollama(system_prompt, query, model=model)
    return response