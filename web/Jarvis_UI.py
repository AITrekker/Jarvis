import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
from datetime import timedelta
import os
import sys
# import json

# Patch torch to prevent Streamlit file watcher errors
try:
    import torch.classes
    import types
    
    # Create a dummy module that won't cause errors when inspected
    class DummyModule(types.ModuleType):
        def __init__(self):
            super().__init__("torch.classes")
            
        def __getattr__(self, item):
            return None
            
        # Add special handling for __path__
        @property
        def __path__(self):
            return []
    
    # Replace torch.classes with our dummy module
    sys.modules['torch.classes'] = DummyModule()
except:
    pass

# Disable telemetry for Streamlit
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_TELEMETRY'] = 'false'

# Add project root to path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.chroma_store import initialize_chroma, get_all_summaries
from utils.summarize import generate_embedding
# Comment out reminders for now
# from utils.reminders import get_reminders, create_reminder, mark_reminder_complete, detect_followups

# Initialize ChromaDB
initialize_chroma(force=True)

# Page configuration
st.set_page_config(
    page_title="Jarvis Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #e6f3ff;
        border-left: 5px solid #2e86de;
    }
    .chat-message.assistant {
        background-color: #f5f5f5;
        border-left: 5px solid #8e44ad;
    }
    .chat-message .message-content {
        margin-top: 0.5rem;
    }
    .highlight {
        background-color: #ffffcc;
        padding: 0.2rem;
        border-radius: 0.2rem;
    }
    .source-link {
        font-size: 0.8rem;
        color: #666;
        text-decoration: none;
    }
    .timeline-card {
        border: 1px solid #ddd;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_date" not in st.session_state:
    st.session_state.selected_date = datetime.date.today()

def search_conversations(query, top_k=5):
    """Search conversations using the query."""
    try:
        embedding = generate_embedding(query)
        from storage.chroma_store import search_summaries
        # Fix: Pass embedding as positional argument instead of named parameter
        results = search_summaries(embedding, top_k=top_k)
        return results
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return []

def highlight_keywords(text, keywords):
    """Highlight keywords in text."""
    highlighted = text
    for keyword in keywords:
        if len(keyword) > 3:  # Only highlight keywords longer than 3 chars
            highlighted = highlighted.replace(keyword, f"<span class='highlight'>{keyword}</span>")
    return highlighted

# Sidebar navigation
st.sidebar.title("🧠 Jarvis Assistant")
# Remove the reminders option
page = st.sidebar.radio("Navigation", ["Memory Search", "Conversation Timeline"])

# Main content based on selected page
if page == "Memory Search":
    st.header("🔍 Search Your Conversation Memory")
    
    search_col1, search_col2 = st.columns([3, 1])
    
    with search_col1:
        search_query = st.text_input("Ask a question or search for topics", 
                                    placeholder="What did we discuss about the hot rod engine?")
    
    with search_col2:
        search_button = st.button("Search", use_container_width=True)
        num_results = st.slider("Number of results", min_value=1, max_value=10, value=3)
    
    # Process search
    if search_button and search_query:
        with st.spinner("Searching your conversation memory..."):
            results = search_conversations(search_query, top_k=num_results)
            st.session_state.search_results = results
            
            if not results:
                st.info("No matching conversations found.")
    
    # Display search results
    if st.session_state.search_results:
        st.subheader("Search Results")
        
        # Extract keywords for highlighting
        keywords = search_query.lower().split()
        
        for i, result in enumerate(st.session_state.search_results):
            date = result["metadata"]["timestamp"].split("T")[0]
            time = result["metadata"]["timestamp"].split("T")[1][:5]
            summary = result["metadata"]["summary"]
            relevance = 100 * (1 - result.get("distance", 0))
            
            with st.expander(f"Conversation on {date} at {time} (Relevance: {relevance:.1f}%)"):
                st.markdown(f"**Date:** {date} at {time}")
                st.markdown(f"**Summary:**")
                st.markdown(highlight_keywords(summary, keywords), unsafe_allow_html=True)
                st.markdown(f"**Source count:** {result['metadata']['source_count']} transcript entries")
                
                # Comment out reminder button
                # if st.button(f"Create followup for this conversation #{i+1}"):
                #     reminder_text = f"Follow up on conversation from {date}: {summary[:100]}..."
                #     due_date = datetime.datetime.now() + timedelta(days=1)
                #     create_reminder(reminder_text, due_date)
                #     st.success("Followup reminder created!")

        # Add to chat history
        if st.button("Start chat with these results"):
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": search_query
            })
            
            # Create assistant response from results
            response = "Here's what I found in your conversations:\n\n"
            for i, result in enumerate(st.session_state.search_results[:3]):
                date = result["metadata"]["timestamp"].split("T")[0]
                summary = result["metadata"]["summary"][:300] + "..."
                response += f"**Conversation {i+1} ({date}):**\n{summary}\n\n"
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })
            
    # Display chat interface if there are messages
    if st.session_state.messages:
        st.subheader("Chat")
        
        for message in st.session_state.messages:
            if message["role"] == "user":
                with st.container():
                    st.markdown(f"""
                    <div class="chat-message user">
                        <div><strong>You</strong></div>
                        <div class="message-content">{message["content"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                with st.container():
                    st.markdown(f"""
                    <div class="chat-message assistant">
                        <div><strong>Jarvis</strong></div>
                        <div class="message-content">{message["content"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Input for continuing the chat
        chat_input = st.chat_input("Ask a follow-up question...")
        if chat_input:
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": chat_input
            })
            
            # Generate response
            with st.spinner("Processing your question..."):
                results = search_conversations(chat_input, top_k=3)
                
                if results:
                    response = "Based on your conversations:\n\n"
                    for i, result in enumerate(results[:3]):
                        date = result["metadata"]["timestamp"].split("T")[0]
                        summary = result["metadata"]["summary"][:300] + "..."
                        response += f"**Conversation {i+1} ({date}):**\n{summary}\n\n"
                else:
                    response = "I couldn't find any relevant information in your conversations."
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
                
                # Comment out followup detection
                # followups = detect_followups(chat_input, results)
                # if followups:
                #     st.info(f"💡 Potential followup detected: {followups[0]}")
                #     if st.button("Add as reminder"):
                #         create_reminder(followups[0], datetime.datetime.now() + timedelta(days=1))
                #         st.success("Reminder added!")
            
            # Force a rerun to show the new messages
            st.rerun()

elif page == "Conversation Timeline":
    st.header("📅 Conversation Timeline")
    
    # Get all summaries
    summaries = get_all_summaries()
    
    if not summaries:
        st.info("No conversation history found.")
    else:
        # Extract dates for the calendar
        dates = []
        conversation_counts = {}
        
        for summary in summaries:
            date_str = summary["metadata"]["timestamp"].split("T")[0]
            dates.append(date_str)
            
            # Count conversations per day
            if date_str in conversation_counts:
                conversation_counts[date_str] += 1
            else:
                conversation_counts[date_str] = 1
        
        # Create date selection
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Create a heatmap calendar
            if dates:
                df = pd.DataFrame({
                    'date': list(conversation_counts.keys()),
                    'count': list(conversation_counts.values())
                })
                df['date'] = pd.to_datetime(df['date'])
                
                # Create a continuous date range
                all_dates = pd.date_range(start=min(df['date']), end=max(df['date']))
                all_df = pd.DataFrame({'date': all_dates})
                
                # Merge to fill in zeros for missing dates
                merged_df = all_df.merge(df, on='date', how='left').fillna(0)
                
                # Create a pivot table for the heatmap
                merged_df['day'] = merged_df['date'].dt.day_name()
                merged_df['week'] = merged_df['date'].dt.isocalendar().week
                
                pivot_df = merged_df.pivot_table(
                    values='count', 
                    index='week', 
                    columns='day', 
                    aggfunc='sum'
                ).fillna(0)
                
                # Create heatmap
                days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                pivot_df = pivot_df.reindex(columns=days_order)
                
                fig = px.imshow(
                    pivot_df,
                    labels=dict(x="Day", y="Week", color="Conversations"),
                    x=days_order,
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            selected_date = st.date_input("Select date", st.session_state.selected_date)
            if selected_date != st.session_state.selected_date:
                st.session_state.selected_date = selected_date
        
        with col3:
            view_mode = st.radio("View mode", ["Day", "Week", "Month"])
        
        # Filter conversations by selected date/period
        filtered_summaries = []
        
        selected_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")
        
        for summary in summaries:
            summary_date_str = summary["metadata"]["timestamp"].split("T")[0]
            
            if view_mode == "Day" and summary_date_str == selected_date_str:
                filtered_summaries.append(summary)
            elif view_mode == "Week":
                summary_date = datetime.datetime.strptime(summary_date_str, "%Y-%m-%d").date()
                start_of_week = st.session_state.selected_date - timedelta(days=st.session_state.selected_date.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                if start_of_week <= summary_date <= end_of_week:
                    filtered_summaries.append(summary)
            elif view_mode == "Month":
                if summary_date_str.startswith(selected_date_str[:7]):  # Compare year-month
                    filtered_summaries.append(summary)
        
        # Display filtered conversations
        if not filtered_summaries:
            st.info(f"No conversations found for the selected {view_mode.lower()}.")
        else:
            st.subheader(f"Conversations ({len(filtered_summaries)})")
            
            # Sort by timestamp
            filtered_summaries.sort(key=lambda x: x["metadata"]["timestamp"], reverse=True)
            
            for summary in filtered_summaries:
                date = summary["metadata"]["timestamp"].split("T")[0]
                time = summary["metadata"]["timestamp"].split("T")[1][:5]
                summary_text = summary["metadata"]["summary"]
                source_count = summary["metadata"]["source_count"]
                
                st.markdown(f"""
                <div class="timeline-card">
                    <h4>{date} at {time}</h4>
                    <p>{summary_text}</p>
                    <small>Based on {source_count} transcript entries</small>
                </div>
                """, unsafe_allow_html=True)

# Removed the entire "Followups & Reminders" page

# Run the app
if __name__ == "__main__":
    pass  # Streamlit already executes the script