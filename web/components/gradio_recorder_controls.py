import gradio as gr
import time
from utils.recorder import start_transcription, pause_transcription, resume_transcription, stop_transcription
from web.web_utils.session import session_state
from setup.logger import logger

def add_to_console(message, error=False):
    """Add a message to the console output in session state."""
    timestamp = time.strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {'❗ ' if error else ''}{message}"
    
    if session_state.console_output is None:
        session_state.console_output = []
        
    session_state.console_output.append(formatted_message)
    # Limit console history
    if len(session_state.console_output) > 100:
        session_state.console_output = session_state.console_output[-100:]
    
    if error:
        logger.error(message)
    else:
        logger.info(message)

    return "\n".join(session_state.console_output[-15:])

def create_recorder_controls():
    """Create the Gradio recorder controls interface."""
    with gr.Blocks() as recorder_interface:
        with gr.Column():
            gr.Markdown("### 🎙️ Recorder Controls")
            
            status_text = gr.Textbox(label="Status", value="⏹️ Stopped", interactive=False)
            
            with gr.Row():
                start_button = gr.Button("▶️ Start")
                pause_button = gr.Button("⏸️ Pause", interactive=False)
                stop_button = gr.Button("⏹️ Stop", interactive=False)
            
            gr.Markdown("### 📟 Console Output")
            console_output = gr.Textbox(label="Console", lines=10, interactive=False, autoscroll=True)

            def start_or_resume_recording_ui():
                if session_state.is_recording and session_state.is_paused:
                    console_str = add_to_console("Resuming transcription...")
                    success = resume_transcription()
                    if success:
                        session_state.is_paused = False
                        console_str = add_to_console("▶️ Recording resumed")
                        return {
                            start_button: gr.update(interactive=False),
                            pause_button: gr.update(interactive=True),
                            stop_button: gr.update(interactive=True),
                            status_text: gr.update(value="▶️ Recording"),
                            console_output: gr.update(value=console_str)
                        }
                    else:
                        console_str = add_to_console("❌ Failed to resume recording", error=True)
                        return {
                            console_output: gr.update(value=console_str)
                        }
                else:
                    console_str = add_to_console("Starting transcription...")
                    success = start_transcription()
                    if success:
                        session_state.is_recording = True
                        session_state.is_paused = False
                        console_str = add_to_console("✅ Recording started successfully!")
                        return {
                            start_button: gr.update(interactive=False),
                            pause_button: gr.update(interactive=True),
                            stop_button: gr.update(interactive=True),
                            status_text: gr.update(value="▶️ Recording"),
                            console_output: gr.update(value=console_str)
                        }
                    else:
                        console_str = add_to_console("❌ Failed to start recording", error=True)
                        return {
                            console_output: gr.update(value=console_str)
                        }

            def pause_recording_ui():
                console_str = add_to_console("Pausing transcription...")
                success = pause_transcription()
                if success:
                    session_state.is_paused = True
                    console_str = add_to_console("⏸️ Recording paused")
                    return {
                        start_button: gr.update(value="▶️ Resume", interactive=True),
                        pause_button: gr.update(interactive=False),
                        stop_button: gr.update(interactive=True),
                        status_text: gr.update(value="⏸️ Paused"),
                        console_output: gr.update(value=console_str)
                    }
                else:
                    console_str = add_to_console("❌ Failed to pause recording", error=True)
                    return {
                        console_output: gr.update(value=console_str)
                    }

            def stop_recording_ui():
                console_str = add_to_console("Stopping transcription...")
                success = stop_transcription()
                if success:
                    console_str = add_to_console("⏹️ Recording stopped")
                else:
                    console_str = add_to_console("⚠️ Had trouble stopping recording cleanly")
                
                session_state.is_recording = False
                session_state.is_paused = False
                return {
                    start_button: gr.update(value="▶️ Start", interactive=True),
                    pause_button: gr.update(interactive=False),
                    stop_button: gr.update(interactive=False),
                    status_text: gr.update(value="⏹️ Stopped"),
                    console_output: gr.update(value=console_str)
                }

            start_button.click(
                start_or_resume_recording_ui,
                outputs=[start_button, pause_button, stop_button, status_text, console_output]
            )
            pause_button.click(
                pause_recording_ui,
                outputs=[start_button, pause_button, stop_button, status_text, console_output]
            )
            stop_button.click(
                stop_recording_ui,
                outputs=[start_button, pause_button, stop_button, status_text, console_output]
            )

    return recorder_interface 