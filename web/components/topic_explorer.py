import streamlit as st
from web.web_utils.search_handler import search_conversations

def render_topic_explorer():
    """Render the Topic Explorer page."""
    st.header("🔍 Explore Topics")
    
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

def handle_topic_search():
    """Handle topic search input."""
    topic_query = st.session_state.topic_query
    if topic_query:
        with st.spinner("Searching for related topics..."):
            search_result = search_conversations(topic_query, top_k=5)
            st.session_state.search_results = search_result
            st.session_state.selected_topic = topic_query