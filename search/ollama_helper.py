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

def get_embedding(text: str, model: str = OLLAMA_MODEL) -> List[float]:
    """
    Generate embeddings for a given text using the Ollama API.
    
    Args:
        text: The text to generate embeddings for
        model: The Ollama model to use for embedding
        
    Returns:
        A list of floats representing the embedding, or an empty list on error.
    """
    try:
        # Use the /api/embeddings endpoint
        url = OLLAMA_URL.replace("/api/generate", "/api/embeddings")
        
        payload = {
            "model": model,
            "prompt": text
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            return response.json().get("embedding", [])
        else:
            logger.error(f"Ollama embedding API error: {response.status_code}, {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Exception when calling Ollama embedding API: {str(e)}")
        return []

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
    """
    # Add this to your rag_search function to help debug
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"RAG Query: '{query}'")
    
    # Extract content from results and ensure we have valid content
    documents = []
    for result in results:
        # Get content from result, with multiple fallbacks
        content = None
        timestamp = result.get("metadata", {}).get("timestamp", "Unknown date")
        
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
            # Calculate relevance using your configuration
            relevance = 0
            if "distance" in result:
                relevance = RAG_RELEVANCE_FACTOR * (1 - result["distance"])
            elif "similarity" in result:
                relevance = RAG_RELEVANCE_FACTOR * result["similarity"]
            else:
                relevance = 50
            documents.append({"content": content, "timestamp": timestamp, "relevance": relevance})
    
    # Now log the document information AFTER creating the documents list
    logger.info(f"Number of documents: {len(documents)}")
    if documents:
        logger.info(f"Top document relevance: {documents[0]['relevance']:.1f}%")
    else:
        logger.info("No documents found")
    
    # If no valid documents found, return error message
    if not documents:
        return "I couldn't find any relevant information to answer your question."
    
    # Sort documents by relevance
    documents.sort(key=lambda x: x["relevance"], reverse=True)
    
    # Build context using your configuration
    context = RAG_CONTEXT_HEADER
    
    for i, doc in enumerate(documents, 1):
        context += RAG_DOCUMENT_HEADER.format(num=i, relevance=doc["relevance"])
        context += RAG_DATE_FORMAT.format(timestamp=doc["timestamp"])
        context += RAG_SUMMARY_FORMAT.format(summary=doc["content"])
    
    # Create full prompt
    system_prompt = OLLAMA_RAG_SYSTEM_PROMPT
    user_prompt = f"{RAG_QUERY_PREFIX}{query}{context}{RAG_FINAL_INSTRUCTION}"
    
    # Generate response
    response = query_ollama(system_prompt, user_prompt, model=model)
    return response