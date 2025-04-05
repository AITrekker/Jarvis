import os
import json
from datetime import datetime, timedelta
from config import TRANSCRIPT_DIR, SUMMARY_INTERVAL_MIN

def save_transcript(transcript_text, timestamp, directory=None, quiet=False):
    """
    Save transcript text to JSON files, aggregated by intervals defined in config.SUMMARY_INTERVAL_MIN.
    Each interval gets its own file, with multiple transcripts stored as entries.
    
    Args:
        transcript_text (str): The transcribed text to save
        timestamp (str): ISO format timestamp
        directory (str, optional): Override directory for testing
        quiet (bool, optional): Suppress output for testing
    """
    # Allow directory override for testing
    save_dir = directory if directory is not None else TRANSCRIPT_DIR
    
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Parse the timestamp
    timestamp_obj = datetime.fromisoformat(timestamp)
    
    # Round down to the nearest interval (as defined in config)
    minute = timestamp_obj.minute
    interval = SUMMARY_INTERVAL_MIN
    rounded_minute = (minute // interval) * interval
    
    # Generate a filename based on the interval (truncate seconds and microseconds)
    interval_timestamp = timestamp_obj.replace(minute=rounded_minute, second=0, microsecond=0)
    filename = f"transcript_{interval_timestamp.isoformat().replace(':', '-')}.json"
    filepath = os.path.join(save_dir, filename)
    
    # Create an entry with the exact timestamp and transcript
    new_entry = {
        "timestamp": timestamp,
        "transcript": transcript_text
    }
    
    # If file exists, append to it; otherwise create a new file
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                try:
                    data = json.load(f)
                    # Check if the file has the expected structure
                    if 'entries' not in data:
                        # Convert old format to new format if needed
                        data = {"entries": [data] if "transcript" in data else []}
                except json.JSONDecodeError:
                    # Handle corrupt files
                    data = {"entries": []}
        except Exception as e:
            # Handle any other file errors
            data = {"entries": []}
    else:
        data = {"entries": []}
    
    # Add the new entry
    data["entries"].append(new_entry)
    
    # Write back to file
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

    if not quiet:
        print(f"Transcript saved to {filepath}")
    
    return filepath

def load_recent_transcripts(since_time):
    print(f"Loading transcripts since {since_time}")
    # TODO: Implement loading from JSON files
    return []
