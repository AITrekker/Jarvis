import json
import requests
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import config
from config import (
    OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE, OLLAMA_MAX_TOKENS, logger
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
            "stream": False,
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

def rag_search(query, search_results, model=None):
    """
    Perform RAG (Retrieval-Augmented Generation) using the search results.
    
    Args:
        query: The user query
        search_results: Retrieved documents from search
        model: The model name to use for generation (optional)
    
    Returns:
        Generated response incorporating the search results
    """
    # If no model is provided, use the default from config
    if model is None:
        model = OLLAMA_MODEL
    
    # Log the number of results for debugging
    logger.debug(f"RAG search found {len(search_results)} results for query: {query}")
    
    # Create system prompt - keeping it simple but effective
    system_prompt = """You are Jarvis, a helpful AI assistant with access to past conversation summaries.
When responding to the user's query, use the provided documents to give accurate, relevant information.
Reference specific information from the documents when appropriate."""
    
    # Format user prompt with retrieved documents - returning to the effective simple format
    user_prompt = f"Query: {query}\n\nRelevant conversation history:\n"
    
    # Add relevant documents to the prompt - keeping the original effective format
    for i, result in enumerate(search_results, 1):
        timestamp = result["metadata"].get("timestamp", "Unknown date")
        summary = result["metadata"].get("summary", "No summary available")
        relevance = 100 * (1 - result["distance"])
        
        user_prompt += f"\n--- Document {i} (Relevance: {relevance:.1f}%) ---\n"
        user_prompt += f"Date: {timestamp}\n"
        user_prompt += f"Summary: {summary}\n"
    
    # Add a final instruction to ensure good use of sources
    user_prompt += "\nPlease provide a helpful response to the query using the relevant information above."
    
    # Call the LLM with the enhanced prompt
    response = query_ollama(system_prompt, user_prompt, model=model)
    
    return response