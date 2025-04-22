import requests
import json
from datetime import datetime, timedelta
import os
import sys

from storage.file_store import load_recent_transcripts
from config import (
    OLLAMA_URL, OLLAMA_MODEL, OLLAMA_EMBEDDING_MODEL,
    OLLAMA_EMBEDDINGS_URL, 
    SUMMARY_INTERVAL_MIN, SUMMARY_DIR,
    SUMMARY_MAX_CHARS, USE_SUMMARY_CHUNKING,
    SUMMARY_FILE_ROLLOVER_MIN 
)
from setup.logger import logger

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
        logger.error(f"Error calling Ollama API: {e}")
        return f"Error generating summary: {e}"

def generate_embedding(text, model=OLLAMA_EMBEDDING_MODEL):
    """Generate embeddings using Ollama"""
    if not text.strip():
        logger.warning("Error: Text for embedding is empty.")
        return []
    try:
        response = requests.post(OLLAMA_EMBEDDINGS_URL, json={
            "model": model,
            "prompt": text,
        })
        response.raise_for_status()
        return response.json().get('embedding', [])
    except requests.exceptions.RequestException as e:
        print(f"Error generating embedding: {e}")
        logger.error(f"Error generating embedding: {e}")
        return []

def create_summary_prompt(transcripts, max_tokens=3000):
    """
    Create a prompt for summarization based on transcript data, with optional chunking.
    """
    if not transcripts:
        return "No transcripts available to summarize."  # Return a STRING, not a LIST

    # Check if transcripts have speaker labels
    has_speakers = any('segments' in entry for entry in transcripts)

    if has_speakers:
        texts = []
        for entry in transcripts:
            segments = entry.get('segments', [])
            if segments:
                for segment in segments:
                    speaker = segment.get('speaker', 'Unknown')
                    text = segment.get('text', '').strip()
                    texts.append(f"{speaker}: {text}")
            else:
                texts.append(entry['transcript'])
    else:
        texts = [entry['transcript'] for entry in transcripts]

    combined_text = "\n".join(texts)

    # Apply chunking only if enabled in config
    if USE_SUMMARY_CHUNKING and len(combined_text) > SUMMARY_MAX_CHARS:
        # Split into multiple chunks instead of truncating
        chunks = []
        start = 0
        while start < len(combined_text):
            end = start + SUMMARY_MAX_CHARS
            if end > len(combined_text):
                end = len(combined_text)
            chunks.append(combined_text[start:end])
            start = end
        
        # Join chunks with a separator
        combined_text = "\n\n[Transcript chunked due to length.]\n\n".join(chunks)

    prompt = f"""Please summarize the following transcribed conversation:
{combined_text}
Provide a concise summary that captures the main points and important details.
Format your response as a simple, well-organized summary without mentioning that this is a summary or transcription.
"""
    return prompt

def summarize_recent_transcripts():
    """
    Summarize transcripts from the last SUMMARY_INTERVAL_MIN minutes
    """
    now = datetime.utcnow()
    
    # Calculate the start of the previous complete interval
    interval = SUMMARY_INTERVAL_MIN
    current_minute = now.minute % interval
    interval_start = now - timedelta(minutes=current_minute, seconds=now.second, microseconds=now.microsecond)
    previous_interval_start = interval_start - timedelta(minutes=interval)
    
    print(f"📝 Summarizing transcripts from {previous_interval_start.strftime('%H:%M')} to {interval_start.strftime('%H:%M')}")
    
    # Get transcripts from the previous complete interval
    transcripts = load_recent_transcripts(previous_interval_start.isoformat())
    
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
    """Save the summary to a file and add its embedding to the vector database."""
    # Import here to avoid circular imports
    from storage.chroma_store import add_summary_embedding

    # Generate the embedding
    embedding = generate_embedding(summary_text)
    
    # Get the time for the current summary
    current_time = datetime.now()
    
    # Generate the filename based on the current timestamp
    timestamp_str = current_time.strftime("%Y-%m-%dT%H-%M-%S")
    
    # Create the summary directory if it doesn't exist
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)
    
    # Get current time for the entry
    now = datetime.utcnow()
    
    # Use configurable rollover interval instead of fixed hourly rollover
    rollover_minutes = SUMMARY_FILE_ROLLOVER_MIN
    current_minute = now.minute
    rollover_minute = (current_minute // rollover_minutes) * rollover_minutes

    # Create filename based on rollover interval
    period_start = now.replace(minute=rollover_minute, second=0, microsecond=0)
    filename = f"summary_{period_start.isoformat().replace(':', '-')}.json"
    filepath = os.path.join(SUMMARY_DIR, filename)
    
    # Generate embedding for the summary
    embedding = generate_embedding(summary_text)

    # Create a summary entry
    new_entry = {
        "timestamp": now.isoformat(),
        "summary": summary_text,
        "source_count": len(source_transcripts),
        "period_minutes": SUMMARY_INTERVAL_MIN,
        "interval_start": (now - timedelta(minutes=SUMMARY_INTERVAL_MIN)).isoformat(),
        "embedding": embedding  # Add embedding to the entry
    }
    
    # If file exists, append to it; otherwise create a new file
    data = {"entries": []}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                if 'entries' not in data:
                    # Convert old format to new format if needed
                    data = {"entries": []}
        except Exception as e:
            print(f"Error reading existing summary file: {e}")
    
    # Add the new entry
    data["entries"].append(new_entry)
    
    # Write back to file
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Summary saved to: {filepath}")
    
    # Add to ChromaDB
    add_summary_embedding(
        embedding=embedding,
        summary_text=summary_text,
        source_transcripts=source_transcripts,
        timestamp=current_time.isoformat()
    )
    
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
