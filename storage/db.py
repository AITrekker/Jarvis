import os
import json
from datetime import datetime, timedelta
from config import TRANSCRIPT_DIR, TRANSCRIPT_AGGREGATION_MIN  # Updated variable name
from setup.logger import logger

def save_transcript(transcript_text, timestamp, directory=None, quiet=False, has_speakers=False):
    """
    Save transcript text to JSON files, aggregated by intervals defined in config.TRANSCRIPT_AGGREGATION_MIN.
    Each interval gets its own file, with multiple transcripts stored as entries.
    
    Args:
        transcript_text (str): The transcribed text to save
        timestamp (str): ISO format timestamp
        directory (str, optional): Override directory for testing
        quiet (bool, optional): Suppress output for testing
        has_speakers (bool, optional): Whether transcript has speaker labels
    """
    # Allow directory override for testing
    save_dir = directory if directory is not None else TRANSCRIPT_DIR
    
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Parse the timestamp
    timestamp_obj = datetime.fromisoformat(timestamp)
    
    # Round down to the nearest interval (as defined in config)
    minute = timestamp_obj.minute
    interval = TRANSCRIPT_AGGREGATION_MIN  # Updated variable name
    rounded_minute = (minute // interval) * interval
    
    # Generate a filename based on the interval (truncate seconds and microseconds)
    interval_timestamp = timestamp_obj.replace(minute=rounded_minute, second=0, microsecond=0)
    filename = f"transcript_{interval_timestamp.isoformat().replace(':', '-')}.json"
    filepath = os.path.join(save_dir, filename)
    
    # Create an entry with the exact timestamp and transcript
    new_entry = {
        "timestamp": timestamp,
        "transcript": transcript_text,
        "has_speakers": has_speakers
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
    """
    Load transcripts created since a specific time
    
    Args:
        since_time (str): ISO format timestamp
        
    Returns:
        list: List of transcript entries
    """
    try:
        # Parse the input timestamp
        since_datetime = datetime.fromisoformat(since_time)
        
        # List to store all matching transcripts
        all_transcripts = []
        
        # Ensure directory exists
        if not os.path.exists(TRANSCRIPT_DIR):
            print(f"Transcript directory not found: {TRANSCRIPT_DIR}")
            return all_transcripts
            
        # Get all JSON files in the transcript directory
        files = [f for f in os.listdir(TRANSCRIPT_DIR) if f.endswith('.json')]
        
        for filename in files:
            try:
                # Parse the timestamp from the filename
                # Format: transcript_YYYY-MM-DDTHH-MM-00.json
                datetime_str = filename.replace('transcript_', '').replace('.json', '')
                file_datetime = datetime.strptime(datetime_str, '%Y-%m-%dT%H-%M-00')
                
                # Only process files that might contain transcripts after since_time
                # (The file's interval might start before since_time but contain later entries)
                if file_datetime >= since_datetime - timedelta(minutes=TRANSCRIPT_AGGREGATION_MIN):
                    filepath = os.path.join(TRANSCRIPT_DIR, filename)
                    
                    # Read the file
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        
                        # If the file has entries
                        if 'entries' in data:
                            # Filter entries by timestamp
                            for entry in data['entries']:
                                entry_datetime = datetime.fromisoformat(entry['timestamp'])
                                if entry_datetime >= since_datetime:
                                    all_transcripts.append(entry)
            except Exception as e:
                print(f"Error processing file {filename}: {e}")
                continue
        
        # Sort transcripts by timestamp
        all_transcripts.sort(key=lambda x: x['timestamp'])
        
        print(f"Loaded {len(all_transcripts)} transcripts since {since_time}")
        return all_transcripts
        
    except Exception as e:
        print(f"Error loading transcripts: {e}")
        return []
