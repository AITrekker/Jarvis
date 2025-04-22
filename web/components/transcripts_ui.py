import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta
from storage.chroma_store import get_all_transcripts

def group_transcripts_by_conversation(transcripts):
    """
    Group transcripts into conversations based on time gaps.
    
    Args:
        transcripts: List of transcript dictionaries
        
    Returns:
        List of conversation groups (each containing transcript dictionaries)
    """
    if not transcripts:
        return []
    
    # Sort by timestamp
    sorted_transcripts = sorted(
        transcripts, 
        key=lambda x: x["metadata"]["timestamp"]
    )
    
    # Group transcripts with gaps less than 2 minutes into conversations
    MAX_GAP_SECONDS = 120  # 2 minutes
    conversations = []
    current_group = [sorted_transcripts[0]]
    
    for i in range(1, len(sorted_transcripts)):
        current = datetime.datetime.fromisoformat(
            sorted_transcripts[i]["metadata"]["timestamp"].replace('Z', '+00:00')
        )
        previous = datetime.datetime.fromisoformat(
            sorted_transcripts[i-1]["metadata"]["timestamp"].replace('Z', '+00:00')
        )
        
        time_diff = (current - previous).total_seconds()
        
        if time_diff <= MAX_GAP_SECONDS:
            # Add to current conversation
            current_group.append(sorted_transcripts[i])
        else:
            # Start a new conversation
            conversations.append(current_group)
            current_group = [sorted_transcripts[i]]
    
    # Add the last group
    if current_group:
        conversations.append(current_group)
        
    return conversations

def render_transcripts():
    """Render the Transcripts page."""
    st.header("🎙️ Conversation Transcripts")
    
    # Get all transcripts
    transcripts = get_all_transcripts()
    
    if not transcripts:
        st.info("No transcripts found.")
        return
        
    # Add filtering options
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Create date filter
        min_date = min([datetime.datetime.fromisoformat(t["metadata"]["timestamp"].replace('Z', '+00:00')).date() 
                       for t in transcripts], default=datetime.date.today())
        max_date = max([datetime.datetime.fromisoformat(t["metadata"]["timestamp"].replace('Z', '+00:00')).date() 
                       for t in transcripts], default=datetime.date.today())
        
        selected_date = st.date_input(
            "Filter by date", 
            value=max_date,
            min_value=min_date,
            max_value=max_date
        )
    
    with col2:
        # Create search filter
        search_term = st.text_input("Search transcripts", placeholder="Enter keywords...")
    
    with col3:
        # Add option to group by conversation
        group_by_conversation = st.checkbox("Group by conversation", value=True)
    
    # Filter by date
    filtered_transcripts = []
    selected_date_str = selected_date.strftime("%Y-%m-%d")
    
    for transcript in transcripts:
        timestamp = transcript["metadata"]["timestamp"]
        transcript_date_str = timestamp.split('T')[0]
        
        if transcript_date_str == selected_date_str:
            # If there's a search term, filter by content
            if search_term:
                if search_term.lower() in transcript["document"].lower():
                    filtered_transcripts.append(transcript)
            else:
                filtered_transcripts.append(transcript)
    
    # Show result count
    if search_term:
        st.write(f"Found {len(filtered_transcripts)} transcript entries matching '{search_term}'")
    else:
        st.write(f"Showing {len(filtered_transcripts)} transcript entries")
    
    # Display the transcripts
    if group_by_conversation and filtered_transcripts:
        # Group and display by conversation
        conversations = group_transcripts_by_conversation(filtered_transcripts)
        
        for i, conversation in enumerate(conversations):
            with st.expander(f"Conversation {i+1} - {len(conversation)} entries", expanded=(i==0)):
                # Get conversation start time for display
                start_time = conversation[0]["metadata"]["timestamp"].split('T')[1][:8]
                st.caption(f"Started at {start_time}")
                
                # Display all transcripts in this conversation
                for transcript in conversation:
                    timestamp = transcript["metadata"]["timestamp"]
                    time = timestamp.split('T')[1][:8]
                    text = transcript["document"]
                    speaker = transcript["metadata"].get("speaker", "Unknown")
                    
                    # Determine speaker style - different colors for user vs assistant
                    if speaker.lower() in ["user", "human", "me"]:
                        container = st.container()
                        container.markdown(f"**You** ({time}):")
                        container.markdown(f">{text}")
                    else:
                        container = st.container()
                        container.markdown(f"**Jarvis** ({time}):")
                        container.info(text)
                    
                    st.markdown("---")
    else:
        # Sort by timestamp (newest first)
        filtered_transcripts.sort(
            key=lambda x: x["metadata"]["timestamp"], 
            reverse=True
        )
        
        # Display transcripts individually
        for transcript in filtered_transcripts:
            timestamp = transcript["metadata"]["timestamp"]
            time = timestamp.split('T')[1][:8]
            text = transcript["document"]
            speaker = transcript["metadata"].get("speaker", "Unknown")
            
            with st.container():
                # Use columns for layout
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    st.write(f"**{time}**")
                    st.caption(f"Speaker: {speaker}")
                    
                with col2:
                    st.info(text)
                
                st.divider()

def get_transcript_calendar_data(transcripts):
    """Process transcript data for calendar view."""
    # Count transcripts by date
    counts = {}
    
    for transcript in transcripts:
        date_str = transcript["metadata"]["timestamp"].split("T")[0]
        
        if date_str in counts:
            counts[date_str] += 1
        else:
            counts[date_str] = 1
            
    return counts