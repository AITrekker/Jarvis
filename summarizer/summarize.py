import requests
import json
from datetime import datetime, timedelta
import os
import sys

from storage.db import load_recent_transcripts
from config import SUMMARY_INTERVAL_MIN, SUMMARY_DIR, OLLAMA_URL, OLLAMA_MODEL

def generate_with_ollama(prompt, model=OLLAMA_MODEL):
    """
    Generate text using Ollama local API
    """
    try:
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=data)
        response.raise_for_status()  # Raise exception for HTTP errors
        return response.json().get('response', '')
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        return f"Error generating summary: {e}"

def create_summary_prompt(transcripts):
    """
    Create a prompt for summarization based on transcript data
    """
    if not transcripts:
        return "No transcripts available to summarize."
    
    texts = [entry['transcript'] for entry in transcripts]
    combined_text = "\n".join(texts)
    
    prompt = f"""Please summarize the following transcribed speech:

{combined_text}

Provide a concise summary that captures the main points and important details. 
Format your response as a simple, well-organized summary without mentioning that this is a summary or transcription.
"""
    return prompt

def summarize_recent_transcripts():
    """
    Summarize transcripts from the last SUMMARY_INTERVAL_MIN minutes
    """
    print(f"📝 Summarizing transcripts from the last {SUMMARY_INTERVAL_MIN} minutes...")
    
    # Get recent transcripts
    since_time = datetime.utcnow() - timedelta(minutes=SUMMARY_INTERVAL_MIN)
    transcripts = load_recent_transcripts(since_time.isoformat())
    
    if not transcripts:
        print("No recent transcripts found to summarize.")
        return None
    
    print(f"Found {len(transcripts)} transcript entries to summarize.")
    
    # Create the prompt and generate summary
    prompt = create_summary_prompt(transcripts)
    
    print("Generating summary with Ollama...")
    summary = generate_with_ollama(prompt)
    
    # Save the summary
    save_summary(summary, transcripts)
    
    print("✅ Summary generated and saved.")
    return summary

def save_summary(summary_text, source_transcripts):
    """
    Save the summary to a file
    """
    # Create the summary directory if it doesn't exist
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)
    
    # Create a timestamp for the filename
    timestamp = datetime.utcnow().isoformat().replace(':', '-')
    
    # Summary object to save
    summary_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": summary_text,
        "source_count": len(source_transcripts),
        "source_transcripts": [t.get('transcript') for t in source_transcripts]
    }
    
    # Save to file
    filename = f"summary_{timestamp}.json"
    filepath = os.path.join(SUMMARY_DIR, filename)
    
    with open(filepath, 'w') as f:
        json.dump(summary_data, f, indent=4)
    
    print(f"Summary saved to: {filepath}")
    return filepath

def summarize_text(text):
    """Legacy function for simple text summarization"""
    print("Summarizing single text...")
    prompt = f"""Please summarize the following text:

{text}

Provide a concise summary that captures the main points."""
    
    return generate_with_ollama(prompt)

if __name__ == "__main__":
    # If run directly, summarize recent transcripts
    summarize_recent_transcripts()
