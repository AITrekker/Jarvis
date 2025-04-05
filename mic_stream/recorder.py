import sounddevice as sd
import numpy as np
import tempfile
import os
import queue
import sys
import soundfile as sf
from datetime import datetime

from config import SAMPLERATE, CHANNELS, CHUNK_DURATION, WHISPER_MODEL
from storage.db import save_transcript

def transcribe_from_mic():
    """
    Main function to continuously transcribe audio from the microphone.
    Records audio chunks, transcribes them using Whisper, and saves meaningful transcripts.
    """
    print("🔊 Listening... Speak into your mic.")

    # Queue for audio chunks
    q = queue.Queue()

    # Callback to capture audio into buffer
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio status: {status}", file=sys.stderr)
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
        # Transcribe
        result = WHISPER_MODEL.transcribe(filename, fp16=False, language="en")
        text = result["text"].strip()

        # Check if transcript is meaningful before saving
        if len(text) > 0 and text.lower() not in ["thank you.", "thanks.", ""]:
            prefix = "📝 Final chunk: " if is_final_chunk else "📝 "
            print(f"{prefix}{text}")
            save_transcript(text, datetime.utcnow().isoformat())
        else:
            context = "final chunk" if is_final_chunk else "audio"
            print(f"⚠️ No meaningful {context} detected, skipping save.")
    finally:
        # Always clean up temp file
        if os.path.exists(filename):
            os.remove(filename)
