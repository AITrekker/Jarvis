import gradio as gr
import logging
import pandas as pd
import plotly.graph_objects as go
from web.web_utils.search_handler import get_all_conversations, delete_conversation

logger = logging.getLogger(__name__)

def create_timeline_plot(conversations):
    """Creates a Plotly timeline graph."""
    if not conversations:
        return go.Figure().update_layout(title="No conversation data available", template="plotly_dark")
        
    df = pd.DataFrame([conv['metadata'] for conv in conversations])
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_counts = df.groupby('date').size().reset_index(name='counts')

    fig = go.Figure(data=[go.Bar(x=daily_counts['date'], y=daily_counts['counts'])])
    fig.update_layout(
        title="Conversation Volume",
        xaxis_title="Date",
        yaxis_title="Number of Conversations",
        template="plotly_dark",
        height=300
    )
    return fig

def format_conversations_to_df(conversations):
    """Formats a list of conversation dicts into a Pandas DataFrame."""
    if not conversations:
        return pd.DataFrame(columns=["ID", "Date", "Summary"])
    
    data = []
    for conv in conversations:
        data.append({
            "ID": conv['id'],
            "Date": conv['metadata'].get('timestamp', 'N/A').split("T")[0],
            "Summary": conv['metadata'].get('summary', 'No summary available.')
        })
    return pd.DataFrame(data)

def create_conversation_timeline_interface():
    """Creates the Gradio interface for the Conversation Timeline."""
    with gr.Blocks(analytics_enabled=False) as timeline_interface:
        selected_conversation_id = gr.State(None)

        with gr.Row():
            refresh_button = gr.Button("Refresh")
            delete_button = gr.Button("Delete Selected Conversation", variant="stop", visible=False)

        with gr.Row():
            timeline_plot = gr.Plot()
        
        with gr.Row():
            conversation_df = gr.DataFrame(
                headers=["ID", "Date", "Summary"],
                interactive=False, # Rows are not clickable by default
                row_count=(10, "fixed"),
                col_count=(3, "fixed")
            )
        
        # This component will display the full text of the selected conversation
        with gr.Row():
            selected_summary_display = gr.Textbox(label="Selected Conversation Summary", lines=5, interactive=False, visible=False)

        def refresh_timeline():
            """Fetches data and refreshes the timeline and conversation list."""
            logger.info("Refreshing conversation timeline...")
            conversations = get_all_conversations()
            plot = create_timeline_plot(conversations)
            df = format_conversations_to_df(conversations)
            return {
                timeline_plot: plot,
                conversation_df: gr.update(value=df, interactive=True),
                delete_button: gr.update(visible=False),
                selected_conversation_id: None,
                selected_summary_display: gr.update(visible=False, value="")
            }

        def handle_select_conversation(evt: gr.SelectData, df: pd.DataFrame):
            """Handles the selection of a conversation in the DataFrame."""
            if evt.index is None:
                return gr.update(visible=False), None, gr.update(visible=False)
            
            selected_row = df.iloc[evt.index[0]]
            conv_id = selected_row["ID"]
            summary_text = selected_row["Summary"]
            
            logger.info(f"Conversation selected: {conv_id}")
            return {
                delete_button: gr.update(visible=True),
                selected_conversation_id: conv_id,
                selected_summary_display: gr.update(visible=True, value=summary_text)
            }
        
        def handle_delete_conversation(conv_id_to_delete):
            """Handles the deletion of the selected conversation."""
            if not conv_id_to_delete:
                gr.Warning("No conversation selected to delete.")
                return gr.skip()
            
            logger.info(f"Attempting to delete conversation ID: {conv_id_to_delete}")
            delete_conversation(conv_id_to_delete)
            gr.Info("Conversation deleted.")
            return refresh_timeline()

        # Wire up event handlers
        refresh_button.click(refresh_timeline, outputs=[
            timeline_plot, conversation_df, delete_button, selected_conversation_id, selected_summary_display
        ])
        
        conversation_df.select(
            handle_select_conversation, 
            inputs=[conversation_df], 
            outputs=[delete_button, selected_conversation_id, selected_summary_display]
        )
        
        delete_button.click(
            handle_delete_conversation,
            inputs=[selected_conversation_id],
            outputs=[timeline_plot, conversation_df, delete_button, selected_conversation_id, selected_summary_display]
        )
        
        timeline_interface.load(refresh_timeline, outputs=[
            timeline_plot, conversation_df, delete_button, selected_conversation_id, selected_summary_display
        ])

    return timeline_interface 