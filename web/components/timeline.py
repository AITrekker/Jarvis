"""
Conversation Timeline Component Module

This module provides a timeline visualization of conversation history,
allowing users to explore conversations chronologically.

Role in the system:
- Displays conversations organized by date and time
- Provides chronological navigation of conversation history
- Visualizes the flow of conversations over time
- Enables filtering and exploration by time periods
- Presents detailed views of selected conversation segments

Used by the main web UI to offer chronological exploration of conversation history.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import time
from datetime import timedelta
from storage.chroma_store import get_all_summaries, delete_summary_by_id

def render_timeline():
    """Render the Conversation Timeline page."""
    st.header("📅 Conversation Timeline")
    
    # Initialize session state for delete confirmation
    if 'delete_summary_id' not in st.session_state:
        st.session_state.delete_summary_id = None
    
    # Handle deletion confirmation if needed
    if st.session_state.delete_summary_id:
        show_delete_confirmation()
        return  # Early return to display only the confirmation dialog
    
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
            render_calendar_heatmap(conversation_counts)
        
        with col2:
            selected_date = st.date_input("Select date", datetime.date.today())
        
        with col3:
            view_mode = st.radio("View mode", ["Day", "Week", "Month"])
        
        render_filtered_conversations(summaries, selected_date, view_mode)

def show_delete_confirmation():
    """Show confirmation dialog for deleting a summary."""
    st.warning("⚠️ Are you sure you want to delete this conversation? This action cannot be undone.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Yes, Delete"):
            try:
                delete_summary_by_id(st.session_state.delete_summary_id)
                st.session_state.delete_summary_id = None
                st.success("Conversation deleted successfully!")
                time.sleep(1)  # Give user a moment to see the success message
                st.rerun()  # Use st.rerun() instead of st.experimental_rerun()
            except Exception as e:
                st.error(f"Error deleting conversation: {str(e)}")
    
    with col2:
        if st.button("Cancel"):
            st.session_state.delete_summary_id = None
            st.rerun()  # Use st.rerun() instead of st.experimental_rerun()

def render_calendar_heatmap(conversation_counts):
    """Render the calendar heatmap visualization."""
    # Create a heatmap calendar
    if conversation_counts:
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

def render_filtered_conversations(summaries, selected_date, view_mode):
    """Render conversations filtered by date and view mode."""
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
        
        # Apply custom CSS for the timeline cards
        st.markdown("""
        <style>
        .timeline-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: #f9f9f9;
            position: relative;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .card-date {
            font-weight: bold;
            font-size: 1.2em;
        }
        .card-content {
            margin-bottom: 10px;
        }
        .card-footer {
            font-size: 0.8em;
            color: #666;
        }
        </style>
        """, unsafe_allow_html=True)
        
        for index, summary in enumerate(filtered_summaries):
            summary_id = summary["id"]
            date = summary["metadata"]["timestamp"].split("T")[0]
            time = summary["metadata"]["timestamp"].split("T")[1][:5]
            summary_text = summary["metadata"]["summary"]
            source_count = summary["metadata"]["source_count"]
            
            with st.container():
                col1, col2 = st.columns([9, 1])
                
                with col1:
                    st.markdown(f"**{date} at {time}**")
                
                with col2:
                    # Delete button
                    if st.button("🗑️", key=f"delete_{summary_id}", help="Delete this conversation"):
                        st.session_state.delete_summary_id = summary_id
                        st.rerun()  # Use st.rerun() instead of st.experimental_rerun()
                
                st.markdown(summary_text)
                st.caption(f"Based on {source_count} transcript entries")
                st.divider()