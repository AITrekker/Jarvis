import gradio as gr
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web_utils.session import initialize_session_state
from components.gradio_chat import create_gradio_chat_interface
from components.gradio_recorder_controls import create_recorder_controls
from components.gradio_model_selector import create_model_selector
from components.gradio_conversation_timeline import create_conversation_timeline_interface

def create_ui():
    """Creates the Gradio UI."""
    
    # Initialize session state. This is a bit of a workaround for Gradio.
    # We call it once, and the state is stored in a global-like singleton pattern.
    initialize_session_state()

    with gr.Blocks(title="Jarvis", theme=gr.themes.Soft()) as demo:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("# Jarvis")
                create_recorder_controls()
                create_model_selector()
            with gr.Column(scale=3):
                with gr.Tabs():
                    with gr.TabItem("Chat"):
                        create_gradio_chat_interface()
                    with gr.TabItem("Conversation Timeline"):
                        create_conversation_timeline_interface()
                
    return demo

if __name__ == "__main__":
    ui = create_ui()
    ui.launch() 