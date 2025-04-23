import os
import glob
from datetime import datetime
from config import TRANSCRIPT_DIR
from setup.logger import logger

def delete_transcripts_in_time_range(start_time, end_time):
    """
    Delete transcript files that fall within the specified time range.
    
    Args:
        start_time (datetime): Start time of the range to delete
        end_time (datetime): End time of the range to delete
        
    Returns:
        int: Number of files deleted
    """
    try:
        # Get all transcript files
        transcript_files = glob.glob(os.path.join(TRANSCRIPT_DIR, "transcript_*.json"))
        
        count = 0
        for file_path in transcript_files:
            # Extract timestamp from filename (format: transcript_YYYY-MM-DDTHH-MM-SS.json)
            filename = os.path.basename(file_path)
            if not filename.startswith("transcript_"):
                continue
                
            try:
                # Extract timestamp part
                timestamp_str = filename.replace("transcript_", "").replace(".json", "")
                # Convert from file format (YYYY-MM-DDTHH-MM-SS) to datetime
                file_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H-%M-%S")
                
                # Check if the file is within the time range
                if start_time <= file_time <= end_time:
                    os.remove(file_path)
                    count += 1
                    logger.debug(f"Deleted transcript file: {filename}")
            except Exception as e:
                logger.error(f"Error processing transcript file {filename}: {e}")
                
        return count
    except Exception as e:
        logger.error(f"Error deleting transcripts in time range: {e}")
        return 0