import gradio as gr
import logging
from web.web_utils.llm_handler import get_available_models
from web.web_utils.session import session_state

logger = logging.getLogger(__name__)

def create_model_selector():
    """Creates a dropdown to select the Ollama model."""
    available_models = get_available_models()
    
    # Set a default model if one isn't already set in the session
    if not session_state.ollama_model and available_models:
        session_state.ollama_model = available_models[0]
        logger.info(f"Default Ollama model set to: {session_state.ollama_model}")
    
    with gr.Row():
        model_selector = gr.Dropdown(
            label="Ollama Model",
            choices=available_models,
            value=session_state.ollama_model,
            interactive=True
        )

    def on_model_change(selected_model):
        session_state.ollama_model = selected_model
        logger.info(f"Ollama model changed to: {selected_model}")
        return selected_model

    model_selector.change(on_model_change, inputs=model_selector, outputs=model_selector)

    return model_selector 