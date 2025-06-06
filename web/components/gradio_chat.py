import gradio as gr
import requests
import json
import logging
import re
from web.web_utils.search_handler import search_conversations
from web.web_utils.session import session_state
from utils.tool_manager import ToolManager
from web.web_utils.llm_handler import get_llm_response

tool_manager = ToolManager()
logger = logging.getLogger(__name__)

def create_gradio_chat_interface():
    with gr.Blocks() as chat_interface:
        with gr.Row():
            mode_selector = gr.Radio(
                ["Chat with Tools", "Search Transcripts"], 
                label="Mode", 
                value="Chat with Tools"
            )
        
        chatbot = gr.Chatbot(
            label="Chat with Jarvis", 
            bubble_full_width=False,
            value=session_state.messages,
            type="messages"
        )
        msg = gr.Textbox(placeholder="Ask Jarvis a question...", label="Your Question")
        clear = gr.Button("Clear")

        def user(user_message, history):
            history.append({"role": "user", "content": user_message})
            return "", history

        def bot(history, mode):
            user_message = history[-1]["content"]
            
            if mode == "Chat with Tools":
                # 1. Route to LLM to decide on tool usage
                tool_prompt = tool_manager.get_tool_prompt(user_message)
                if not tool_prompt:
                    logger.warning("Could not generate tool prompt. Falling back to direct LLM call.")
                    # Fallback to direct LLM if no tools are found
                    response = get_llm_response(user_message, session_state.ollama_model)
                    history.append({"role": "assistant", "content": response})
                    return history

                try:
                    llm_decision_str = get_llm_response(tool_prompt, session_state.ollama_model)
                    logger.info(f"LLM raw tool decision response: '{llm_decision_str}'")
                    
                    # Clean the response to ensure it's valid JSON
                    json_match = re.search(r'\{.*\}', llm_decision_str, re.DOTALL)
                    if json_match:
                        llm_decision_str = json_match.group(0)
                    
                    llm_decision = json.loads(llm_decision_str)
                    logger.info(f"LLM parsed tool decision: {llm_decision}")
                    
                    tool_name = llm_decision.get("tool")
                    confidence = llm_decision.get("confidence", 0)
                    
                    # Extract all other potential parameters
                    params = {k: v for k, v in llm_decision.items() if k not in ["tool", "confidence"]}

                    # 2. If a tool is chosen with high confidence, execute it
                    if tool_name and confidence >= 0.8:
                        logger.info(f"LLM decided to use tool '{tool_name}' with confidence {confidence}")
                        try:
                            mcp_response = requests.post(
                                f"http://localhost:5000/tool/{tool_name}",
                                json=params,
                                timeout=10
                            )
                            mcp_response.raise_for_status()
                            tool_result = mcp_response.json()
                            
                            if "error" in tool_result:
                                response = f"Tool '{tool_name}' returned an error: {tool_result['error']}"
                            elif tool_name == "get-forecast":
                                response = f"Weather in {tool_result.get('location', 'N/A')}: {tool_result.get('forecast', 'N/A')}"
                            elif tool_name == "get-time":
                                response = f"Time in {tool_result.get('location', 'N/A')}: {tool_result.get('time', 'N/A')} on {tool_result.get('date', 'N/A')}"
                            elif tool_name == "web-search":
                                results_str = "\n".join([f"- {r}" for r in tool_result.get('results', [])])
                                response = f"Web search results for '{tool_result.get('query')}':\n{results_str}"
                            else:
                                response = json.dumps(tool_result, indent=2)

                            history.append({"role": "assistant", "content": response})
                            return history

                        except requests.exceptions.RequestException as e:
                            logger.error(f"MCP server request failed: {e}")
                            response = f"Error: Could not connect to the tool server. Is it running?"
                            history.append({"role": "assistant", "content": response})
                            return history
                    else:
                        # 3. If no tool is chosen, fall back to a direct LLM call
                        logger.info("No tool selected, falling back to direct LLM call.")
                        response = get_llm_response(user_message, session_state.ollama_model)
                        history.append({"role": "assistant", "content": response})
                        return history

                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to parse LLM tool decision. Raw response was: '{llm_decision_str}'", exc_info=True)
                    # Fallback to direct LLM if parsing fails
                    response = get_llm_response(user_message, session_state.ollama_model)
                    history.append({"role": "assistant", "content": response})
                    return history
            
            elif mode == "Search Transcripts":
                # This is the existing RAG functionality
                model = session_state.ollama_model
                search_result = search_conversations(user_message, top_k=5, model=model)
                
                if search_result and "rag_response" in search_result:
                    response = search_result["rag_response"]
                    sources = []
                    for result in search_result["raw_results"]:
                        relevance = 100 * (1 - result["distance"]) if "distance" in result else 100 * result.get("similarity", 0)
                        sources.append(f"**Result (Relevance: {relevance:.1f}%)**\n{result['metadata']['summary']}\n---")
                    response_with_sources = f"{response}\n\n**Sources:**\n" + "\n".join(sources)
                    history.append({"role": "assistant", "content": response_with_sources})
                else:
                    response = "I couldn't find any relevant information in your conversations."
                    history.append({"role": "assistant", "content": response})

            return history

        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot, [chatbot, mode_selector], chatbot
        )
        
        def clear_chat():
            session_state.messages = []
            return []

        clear.click(clear_chat, None, chatbot, queue=False)

    return chat_interface 