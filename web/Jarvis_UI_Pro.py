import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
from datetime import timedelta
import os
import sys

# Disable telemetry for Streamlit
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_TELEMETRY'] = 'false'

# Add project root to path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage.chroma_store import initialize_chroma, get_all_summaries
from search.search_engine import unified_search
from utils.summarize import generate_embedding

# Import config
from config import (
    UI_PAGE_TITLE, UI_PAGE_ICON, UI_LAYOUT, UI_SIDEBAR_STATE,
    UI_DEFAULT_MODELS, UI_DEFAULT_MODEL, SEARCH_DEFAULT_TOP_K
)

# Initialize ChromaDB
initialize_chroma(force=True)

# Page configuration - use config values
st.set_page_config(
    page_title=UI_PAGE_TITLE,
    page_icon=UI_PAGE_ICON,
    layout=UI_LAYOUT,
    initial_sidebar_state=UI_SIDEBAR_STATE
)

# Add custom CSS for better UI
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
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None

# Sidebar navigation
st.sidebar.title("🤖 Jarvis Assistant Pro")

# Add model selection to sidebar - use config values
available_models = UI_DEFAULT_MODELS
selected_model = st.sidebar.selectbox("Ollama Model", available_models, index=available_models.index(UI_DEFAULT_MODEL))

# Set the selected model in session state
if "ollama_model" not in st.session_state:
    st.session_state.ollama_model = selected_model
elif st.session_state.ollama_model != selected_model:
    st.session_state.ollama_model = selected_model

# Update search function to use config
def search_conversations(query, top_k=SEARCH_DEFAULT_TOP_K):
    """Search conversations using the query with RAG."""
    try:
        # Generate embedding for the query
        embedding = generate_embedding(query)
        
        # Use unified search function
        return unified_search(
            query=query, 
            embedding=embedding, 
            top_k=top_k, 
            use_rag=True,
            model=st.session_state.ollama_model
        )
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

page = st.sidebar.radio("Navigation", ["Chat", "Topic Explorer", "Conversation Timeline"])

# Chat Page
if page == "Chat":
    st.header("💬 Chat with Jarvis")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Input for new message with "Enter to Search"
    def handle_chat_input():
        prompt = st.session_state.chat_input
        if prompt:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response from search
            with st.chat_message("assistant"):
                with st.spinner("Searching conversations..."):
                    # Search with RAG enhancement
                    search_result = search_conversations(prompt, top_k=5)
                    
                    if search_result and "rag_response" in search_result:
                        # Display the RAG-enhanced response
                        st.markdown(search_result["rag_response"])
                        
                        # Add "View Source Results" expander
                        with st.expander("View Source Results"):
                            for i, result in enumerate(search_result["raw_results"], 1):
                                date = result["metadata"]["timestamp"].split("T")[0]
                                summary = result["metadata"]["summary"]
                                relevance = 100 * (1 - result["distance"])
                                st.markdown(f"**Result {i} - {date} (Relevance: {relevance:.1f}%)**")
                                st.markdown(summary)
                                st.markdown("---")
                    else:
                        st.markdown("I couldn't find any relevant information in your conversations.")
            
            # Add assistant response to chat history
            if search_result and "rag_response" in search_result:
                st.session_state.messages.append({"role": "assistant", "content": search_result["rag_response"]})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "I couldn't find any relevant information in your conversations."})
    
    # Add input field with callback
    st.text_input(
        "Ask Jarvis a question...",
        key="chat_input",
        on_change=handle_chat_input,
        placeholder="Type your question and press Enter..."
    )

# Topic Explorer Page
elif page == "Topic Explorer":
    st.header("🔍 Explore Topics")
    
    # Input for topic search with "Enter to Search"
    def handle_topic_search():
        topic_query = st.session_state.topic_query
        if topic_query:
            with st.spinner("Searching for related topics..."):
                search_result = search_conversations(topic_query, top_k=5)
                st.session_state.search_results = search_result
                st.session_state.selected_topic = topic_query
    
    # Add input field with callback
    st.text_input(
        "Enter a topic to explore",
        key="topic_query",
        on_change=handle_topic_search,
        placeholder="e.g., hot rod engine, Wild West party"
    )
    
    # Display results
    if st.session_state.search_results:
        st.subheader(f"Results for: {st.session_state.selected_topic}")
        
        # Display the RAG-enhanced summary first
        if "rag_response" in st.session_state.search_results:
            st.markdown("### AI Analysis")
            st.markdown(st.session_state.search_results["rag_response"])
            st.markdown("---")
            
            # Display source results
            st.markdown("### Source Conversations")
            for i, result in enumerate(st.session_state.search_results["raw_results"]):
                date = result["metadata"]["timestamp"].split("T")[0]
                summary = result["metadata"]["summary"]
                relevance = 100 * (1 - result["distance"])
                with st.expander(f"Conversation on {date} (Relevance: {relevance:.1f}%)"):
                    st.markdown(f"**Summary:** {summary}")
                    st.markdown(f"**Source count:** {result['metadata']['source_count']} transcript entries")

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
            selected_date = st.date_input("Select date", datetime.date.today())
        
        with col3:
            view_mode = st.radio("View mode", ["Day", "Week", "Month"])
        
        # Filter conversations by selected date/period
        filtered_summaries = []
        
        selected_date_str = selected_date.strftime("%Y-%m-%d")
        
        for summary in summaries:
            summary_date_str = summary["metadata"]["timestamp"].split("T")[0]
            
            if view_mode == "Day" and summary_date_str == selected_date_str:
                filtered_summaries.append(summary)
            elif view_mode == "Week":
                summary_date = datetime.datetime.strptime(summary_date_str, "%Y-%m-%d").date()
                start_of_week = selected_date - timedelta(days=selected_date.weekday())
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