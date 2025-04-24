"""
Recorder Control Component Module

This module provides UI elements for controlling the audio recorder functionality
within the Jarvis web application.

Role in the system:
- Displays recording status and controls
- Handles start, stop, pause, and resume actions
- Updates the UI based on recorder state changes
- Provides visual feedback for recording activity
- Connects UI actions to the recorder backend functionality

Used by the main web UI to allow users to control voice recording.
"""

import streamlit as st
import time
import threading
from utils.recorder import start_transcription, pause_transcription, resume_transcription, stop_transcription
from utils.periodic_tasks import start_scheduler, stop_scheduler
from setup.logger import logger
import sys

def render_recorder_controls():
    """Render microphone recording control buttons with console output."""
    st.sidebar.markdown("### 🎙️ Recorder Controls")

    # Initialize recording state if not present
    if "is_recording" not in st.session_state:
        st.session_state.is_recording = False
    if "is_paused" not in st.session_state:
        st.session_state.is_paused = False
    if "console_output" not in st.session_state:
        st.session_state.console_output = []

    # Create a container for status indicator
    status_container = st.sidebar.container()

    # Display current status based on state
    if st.session_state.is_recording and not st.session_state.is_paused:
        status_container.markdown("#### Status: 🔴 Recording")
    elif st.session_state.is_recording and st.session_state.is_paused:
        status_container.markdown("#### Status: ⏸️ Paused")
    else:
        status_container.markdown("#### Status: ⏹️ Stopped")

    col1, col2, col3 = st.sidebar.columns(3)

    # --- Button Styling (kept as is) ---
    col1.markdown("""
    <style>
    div[data-testid="column"]:nth-child(1) button { background-color: white; color: #28a745; }
    div[data-testid="column"]:nth-child(1) button:hover { background-color: #28a745 !important; color: white !important; }
    </style>""", unsafe_allow_html=True)
    col2.markdown("""
    <style>
    div[data-testid="column"]:nth-child(2) button { background-color: white; color: #ff9900; }
    div[data-testid="column"]:nth-child(2) button:hover { background-color: #ff9900 !important; color: white !important; }
    </style>""", unsafe_allow_html=True)
    col3.markdown("""
    <style>
    div[data-testid="column"]:nth-child(3) button { background-color: white; color: #dc3545; }
    div[data-testid="column"]:nth-child(3) button:hover { background-color: #dc3545 !important; color: white !important; }
    </style>""", unsafe_allow_html=True)
    # --- End Button Styling ---

    # --- State Machine Logic for Button Enabling/Disabling ---
    start_text = "▶️ Start"
    start_disabled = False
    pause_disabled = True
    stop_disabled = True

    if st.session_state.is_recording:
        if st.session_state.is_paused:
            # State: Paused
            start_text = "▶️ Resume" # Change text to Resume
            start_disabled = False
            pause_disabled = True
            stop_disabled = False
        else:
            # State: Recording
            start_text = "▶️ Start"
            start_disabled = True
            pause_disabled = False
            stop_disabled = False
    # Else: Initial/Stopped state (defaults are correct)

    # --- Render Buttons ---
    if col1.button(start_text, disabled=start_disabled, use_container_width=True):
        start_or_resume_recording()

    if col2.button("⏸️ Pause", disabled=pause_disabled, use_container_width=True):
        pause_recording()

    if col3.button("⏹️ Stop", disabled=stop_disabled, use_container_width=True):
        stop_recording()

    # --- Console Output ---
    st.sidebar.markdown("### 📟 Console Output")
    console_placeholder = st.sidebar.empty()
    console_text = "\n".join(st.session_state.console_output[-15:])
    console_placeholder.code(console_text, language="bash")
    # --- End Console Output ---

# --- Callback Functions ---

def start_or_resume_recording():
    """Handles starting a new recording or resuming a paused one."""
    if st.session_state.is_recording and not st.session_state.is_paused:
        add_to_console("Already recording.", error=True)
        return

    try:
        if st.session_state.is_recording and st.session_state.is_paused:
            # --- Resume Logic ---
            add_to_console("Resuming transcription...")
            success = resume_transcription()
            
            if success:
                st.session_state.is_paused = False
                add_to_console("▶️ Recording resumed")
            else:
                add_to_console("❌ Failed to resume recording", error=True)
        else:
            # --- Start New Recording Logic ---
            add_to_console("Starting periodic task scheduler...")
            start_scheduler()
            
            add_to_console("Starting transcription...")
            success = start_transcription()
            
            if success:
                st.session_state.is_recording = True
                st.session_state.is_paused = False
                add_to_console("✅ Recording started successfully!")
            else:
                add_to_console("❌ Failed to start recording", error=True)

        st.rerun()
    except Exception as e:
        add_to_console(f"❌ Error starting/resuming recording: {str(e)}", error=True)
        # Reset state on error
        st.session_state.is_recording = False
        st.session_state.is_paused = False
        st.rerun()

def pause_recording():
    """Pauses the recording state."""
    if not st.session_state.is_recording or st.session_state.is_paused:
        add_to_console("Cannot pause: Not recording or already paused.", error=True)
        return

    try:
        add_to_console("Pausing transcription...")
        success = pause_transcription()
        
        if success:
            st.session_state.is_paused = True
            add_to_console("⏸️ Recording paused")
        else:
            add_to_console("❌ Failed to pause recording", error=True)
            
        st.rerun()
    except Exception as e:
        add_to_console(f"❌ Error pausing recording: {str(e)}", error=True)

def stop_recording():
    """Stops the recording state and associated tasks."""
    if not st.session_state.is_recording:
        add_to_console("Cannot stop: Not recording.", error=True)
        return

    try:
        add_to_console("Stopping transcription...")
        success = stop_transcription()
        
        add_to_console("Stopping scheduler...")
        stop_scheduler()
        
        if success:
            add_to_console("⏹️ Recording stopped")
        else:
            add_to_console("⚠️ Had trouble stopping recording cleanly")
        
        st.session_state.is_recording = False
        st.session_state.is_paused = False
        
        st.rerun()
    except Exception as e:
        add_to_console(f"❌ Error stopping recording: {str(e)}", error=True)
        # Reset state even on error
        st.session_state.is_recording = False
        st.session_state.is_paused = False
        st.rerun()

# --- Console Helper ---
def add_to_console(message, error=False):
    """Add a message to the console output."""
    timestamp = time.strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {'❗ ' if error else ''}{message}"
    
    if "console_output" in st.session_state:
        st.session_state.console_output.append(formatted_message)
        # Limit console history
        if len(st.session_state.console_output) > 100:
            st.session_state.console_output = st.session_state.console_output[-100:]
    
    if error:
        logger.error(message)
    else:
        logger.info(message)