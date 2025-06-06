import requests
import json
import logging

logger = logging.getLogger(__name__)

def get_available_models():
    """Gets a list of available models from the Ollama API."""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        response.raise_for_status()
        models = [model['name'] for model in response.json().get('models', [])]
        return models
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Ollama to fetch models: {e}")
        return []
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from Ollama models response.")
        return []

def get_llm_response(prompt, model):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "json": True,
                "temperature": 0
            })
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling LLM: {e}")
        return f'{{"error": "Could not connect to the LLM. Please ensure Ollama is running.", "details": "{e}"}}'
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from LLM response: {e}")
        # The response may not be available if the request failed, so handle that case
        try:
            raw_response = response.text
            logger.error(f"Raw LLM response: {raw_response}")
            return raw_response
        except NameError:
            return '{"error": "Failed to get a response from the LLM."}' 