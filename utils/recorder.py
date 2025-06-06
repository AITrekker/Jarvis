"""
Audio Recording and Transcription Module

This module provides functionality for real-time audio recording, transcription,
and processing of spoken conversations.

Role in the system:
- Captures audio input from the system microphone
- Processes audio chunks in real-time using Whisper model
- Detects speaker changes based on pauses and conversation patterns
- Saves transcribed text to the file storage system
- Manages recording state (start, pause, resume, stop)
- Triggers summarization of transcribed content

Used as the primary audio input system for Jarvis, allowing continuous
recording and transcription of conversations for later search and reference.
Controls the audio processing lifecycle with thread-safe management of resources.
"""

import sounddevice as sd
import numpy as np
import tempfile
import os
import queue
import sys
import threading
import soundfile as sf
from datetime import datetime
from setup.logger import logger
import time

from config import SAMPLERATE, CHANNELS, CHUNK_DURATION, WHISPER_MODEL
from storage.file_store import save_transcript
from utils.summarize import summarize_recent_transcripts

# Global variables to control recording
_recording_active = False
_paused = False
_stop_signal = threading.Event()
_shutdown_complete = threading.Event()  # Add this to signal full shutdown
_recording_thread = None
_audio_stream = None
_audio_queue = None

def start_transcription():
    """Start the transcription process in a background thread."""
    global _recording_active, _recording_thread, _stop_signal, _paused
    
    if _recording_active:
        logger.info("Transcription is already running")
        return False
    
    # Reset control flags
    _stop_signal.clear()
    _paused = False
    
    # Start in a background thread
    _recording_thread = threading.Thread(target=transcribe_from_mic)
    _recording_thread.daemon = True
    _recording_thread.start()
    
    _recording_active = True
    logger.info("Transcription started in background thread")
    return True

def pause_transcription():
    """Pause the transcription process without stopping it completely."""
    global _paused, _recording_active
    
    if not _recording_active:
        logger.info("No transcription is currently running")
        return False
    
    if _paused:
        logger.info("Transcription is already paused")
        return False
    
    logger.info("Pausing transcription...")
    _paused = True
    return True

def resume_transcription():
    """Resume a paused transcription."""
    global _paused, _recording_active
    
    if not _recording_active:
        logger.info("No transcription is currently running")
        return False
    
    if not _paused:
        logger.info("Transcription is not paused")
        return False
    
    logger.info("Resuming transcription...")
    _paused = False
    return True

def stop_transcription():
    """Stop the transcription process and process any remaining audio."""
    global _recording_active, _stop_signal, _paused, _shutdown_complete
    
    if not _recording_active:
        logger.info("No transcription is currently running")
        return False
    
    logger.info("Stopping transcription...")
    _stop_signal.set()
    _paused = False  # Clear pause state
    
    # Wait for the thread to complete processing
    if _recording_thread:
        logger.info("Waiting for recording thread to finish...")
        _recording_thread.join(timeout=30)  # Wait up to 30 seconds
        
        # If thread is still alive after timeout, log warning but continue
        if _recording_thread.is_alive():
            logger.warning("Recording thread did not exit cleanly within timeout")
    
    # Wait for shutdown to complete
    _shutdown_complete.wait(timeout=3)
    
    _recording_active = False
    logger.info("Transcription stopped")
    return True

def transcribe_from_mic():
    """Main function to continuously transcribe audio from the microphone."""
    global _recording_active, _stop_signal, _audio_stream, _audio_queue, _paused, _shutdown_complete
    
    # Reset state for a clean start
    _shutdown_complete.clear()
    _recording_active = True
    _paused = False
    _audio_queue = queue.Queue()
    
    print("🔊 Listening... Speak into your mic.")
    
    # Callback to capture audio into buffer
    def audio_callback(indata, frames, time, status):
        # First check if we should be processing audio at all
        if _stop_signal.is_set() or not _recording_active:
            return
            
        if status:
            #logger.warning(f"⚠️ Audio status: {status}")
            print(f"⚠️ Audio status: {status}", file=sys.stderr)
        
        # Only queue if not paused, active, and queue exists
        if not _paused and _audio_queue is not None:
            try:
                _audio_queue.put(indata.copy())
            except Exception as e:
                logger.error(f"Error in audio callback: {e}")

    try:
        # Open a stream from your microphone
        _audio_stream = sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, callback=audio_callback)
        
        with _audio_stream:
            try:
                audio_buffer = np.empty((0, CHANNELS), dtype=np.float32)
                
                # Continue until explicitly stopped or keyboard interrupt
                while not _stop_signal.is_set():
                    # If paused, just sleep briefly and check flags again
                    if _paused:
                        time.sleep(0.1)
                        continue
                        
                    try:
                        # Use timeout to regularly check stop/pause flags
                        data = _audio_queue.get(timeout=0.2)
                        audio_buffer = np.append(audio_buffer, data, axis=0)
                        
                        # Process when we have enough audio
                        if len(audio_buffer) >= SAMPLERATE * CHUNK_DURATION:
                            process_audio_chunk(audio_buffer)
                            audio_buffer = np.empty((0, CHANNELS), dtype=np.float32)
                            
                    except queue.Empty:
                        # Timeout occurred, just continue and check flags again
                        continue

            except KeyboardInterrupt:
                print("\n🛑 Stopping by user request. Processing last audio chunk...")
                
            finally:
                # Process any meaningful remaining audio
                if len(audio_buffer) > SAMPLERATE * 1:  # At least 1 second
                    try:
                        print("\n🔄 Processing final audio chunk...")
                        process_audio_chunk(audio_buffer, is_final_chunk=True)
                    except Exception as e:
                        logger.error(f"Error processing final chunk: {e}")
                        print(f"Error processing final chunk: {e}")
                else:
                    print("⚠️ Final audio chunk too short, skipping.")
                
                # Run final summarization
                print("\n📋 Running final summarization...")
                try:
                    summary = summarize_recent_transcripts()
                    if summary:
                        print("\nFINAL SUMMARY:")
                        print("=" * 50)
                        print(summary)
                        print("=" * 50)
                    else:
                        print("No final summary generated (no recent transcripts)")
                except Exception as e:
                    logger.error(f"Error generating final summary: {e}")
                    print(f"Error generating final summary: {e}")
    
    except Exception as e:
        logger.error(f"Error in transcription: {e}")
    
    finally:
        # Important: Clean up all resources in proper sequence
        # Clear all flags and resources
        try:
            if _audio_stream is not None and _audio_stream.active:
                logger.info("Closing audio stream...")
                _audio_stream.stop()
                _audio_stream.close()
        except Exception as e:
            logger.error(f"Error closing audio stream: {e}")
            
        # Clear all resources
        logger.info("Cleaning up resources...")
        _recording_active = False
        
        # Set the queue to None last, after _recording_active is False
        # This ensures the callback won't try to use it anymore
        _audio_queue = None
        _audio_stream = None
        
        # Signal that shutdown is complete
        _shutdown_complete.set()
        
        print("✅ Exited gracefully.")

# For backward compatibility with direct calls
if __name__ == "__main__" or any("python" in arg for arg in sys.argv):
    try:
        transcribe_from_mic()
    except KeyboardInterrupt:
        print("\n🛑 Exiting by keyboard interrupt.")

# Keep the rest of the file unchanged
def process_audio_chunk(audio_buffer, is_final_chunk=False):
    """Process an audio buffer by transcribing and saving meaningful text."""
    # Save to temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        filename = f.name
        sf.write(filename, audio_buffer, SAMPLERATE)
    
    try:
        # Transcribe with segments
        result = WHISPER_MODEL.transcribe(
            filename, 
            fp16=False, 
            language="en",
            verbose=False
        )
        text = result["text"].strip()

        # Check if transcript is meaningful before saving
        if len(text) > 0 and text.lower() not in ["thank you.", "thanks.", ""]:
            prefix = "📝 Final chunk: " if is_final_chunk else "📝 "
            
            # Process segments if available
            if 'segments' in result and len(result['segments']) > 0:
                formatted_text = format_segments(result['segments'])
                print(f"{prefix}\n{formatted_text}")
                # Changed has_speakers to False since we're not including speaker labels anymore
                save_transcript(formatted_text, datetime.utcnow().isoformat(), has_speakers=False)
            else:
                # Fall back to regular text
                print(f"{prefix}{text}")
                save_transcript(text, datetime.utcnow().isoformat())
        else:
            context = "final chunk" if is_final_chunk else "audio"
            print(f"⚠️ No meaningful {context} detected, skipping save.")
    finally:
        # Clean up temp file
        if os.path.exists(filename):
            os.remove(filename)

def format_segments(segments):
    """Format transcript segments with line breaks for speaker changes but no speaker labels"""
    formatted_lines = []
    current_text = []
    
    for i, segment in enumerate(segments):
        text = segment['text'].strip()
        if not text:
            continue
            
        # Speaker detection
        new_speaker = detect_speaker_change(segment, segments, i)
        
        if new_speaker and i > 0 and current_text:
            # Save previous speaker's text and start a new paragraph
            formatted_lines.append(' '.join(current_text))
            current_text = []
                
        # Add this segment's text
        current_text.append(text)
    
    # Add the final text
    if current_text:
        formatted_lines.append(' '.join(current_text))
    
    return "\n".join(formatted_lines)

def detect_speaker_change(current_segment, all_segments, index):
    """Detect if this segment likely has a different speaker"""
    if index == 0:
        return True  # First segment is always a new speaker
        
    prev = all_segments[index-1]
    curr = current_segment
    
    # Check for significant pause (over 1 second)
    if curr['start'] - prev['end'] > 1.0:
        return True
        
    # Check for question/answer pattern
    if prev['text'].strip().endswith('?') and not curr['text'].strip().endswith('?'):
        return True
        
    # Check for pronoun flips indicating conversation
    prev_words = prev['text'].lower().split()
    curr_words = curr['text'].lower().split()
    
    if ('i' in prev_words and 'you' in curr_words) or ('you' in prev_words and 'i' in curr_words):
        return True
    
    return False
