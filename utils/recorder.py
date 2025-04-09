import sounddevice as sd
import numpy as np
import tempfile
import os
import queue
import sys
import soundfile as sf
from datetime import datetime
from setup.logger import logger

from config import SAMPLERATE, CHANNELS, CHUNK_DURATION, WHISPER_MODEL
from storage.db import save_transcript
from utils.summarize import summarize_recent_transcripts

def transcribe_from_mic():
    """
    Main function to continuously transcribe audio from the microphone.
    Records audio chunks, transcribes them using Whisper, and saves meaningful transcripts.
    """
    print("🔊 Listening... Speak into your mic.")
    logger.info("🔊 Listening... Speak into your mic.")
    # Queue for audio chunks
    q = queue.Queue()

    # Callback to capture audio into buffer
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio status: {status}", file=sys.stderr)
            logger.warning(f"⚠️ Audio status: {status}")
        q.put(indata.copy())

    # Open a stream from your microphone
    with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, callback=audio_callback):
        try:
            while True:
                audio_buffer = np.empty((0, CHANNELS), dtype=np.float32)

                # Collect CHUNK_DURATION seconds of audio
                while len(audio_buffer) < SAMPLERATE * CHUNK_DURATION:
                    audio_buffer = np.append(audio_buffer, q.get(), axis=0)

                process_audio_chunk(audio_buffer)

        except KeyboardInterrupt:
            print("\n🛑 Stopping by user request. Processing last audio chunk...")
            # Process any remaining audio data when user hits Ctrl+C
            if len(audio_buffer) > 0:
                try:
                    # Only process if we have enough audio to be meaningful
                    if len(audio_buffer) > SAMPLERATE * 1:  # At least 1 second
                        process_audio_chunk(audio_buffer, is_final_chunk=True)
                    else:
                        print("⚠️ Final audio chunk too short, skipping.")
                except Exception as e:
                    print(f"Error processing final chunk: {e}")
            
            # Run one final summarization
            print("\n📋 Running final summarization...")
            summary = summarize_recent_transcripts()
            if summary:
                print("\nFINAL SUMMARY:")
                print("=" * 50)
                print(summary)
                print("=" * 50)
            else:
                print("No final summary generated (no recent transcripts)")
            
            print("✅ Exited gracefully.")

def process_audio_chunk(audio_buffer, is_final_chunk=False):
    """
    Process an audio buffer by transcribing and saving meaningful text.
    
    Args:
        audio_buffer: NumPy array containing audio data
        is_final_chunk: Boolean indicating if this is the final chunk before exit
    """
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
                save_transcript(formatted_text, datetime.utcnow().isoformat(), has_speakers=True)
            else:
                # Fall back to regular text
                print(f"{prefix}{text}")
                save_transcript(text, datetime.utcnow().isoformat())
        else:
            context = "final chunk" if is_final_chunk else "audio"
            print(f"⚠️ No meaningful {context} detected, skipping save.")
    finally:
        # Always clean up temp file
        if os.path.exists(filename):
            os.remove(filename)

def format_segments(segments):
    """Format transcript segments with simple speaker detection"""
    segments_text = []
    current_speaker = None
    current_text = []
    
    for i, segment in enumerate(segments):
        text = segment['text'].strip()
        if not text:
            continue
            
        # Simple speaker detection based on timing and text patterns
        new_speaker = detect_speaker_change(segment, segments, i)
        
        if new_speaker or current_speaker is None:
            # Save previous speaker's text
            if current_speaker is not None and current_text:
                segments_text.append(f"{current_speaker}: {' '.join(current_text)}")
                current_text = []
                
            # Assign a new speaker
            current_speaker = f"Speaker {len(segments_text) % 2 + 1}"
            
        # Add this segment's text
        current_text.append(text)
    
    # Add the final speaker's text
    if current_speaker and current_text:
        segments_text.append(f"{current_speaker}: {' '.join(current_text)}")
    
    return "\n".join(segments_text)

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
        
    # Check for "I" vs "You" flips
    prev_words = prev['text'].lower().split()
    curr_words = curr['text'].lower().split()
    
    if ('i' in prev_words and 'you' in curr_words) or ('you' in prev_words and 'i' in curr_words):
        # Possible speaker change when pronouns flip
        return True
    
    return False
