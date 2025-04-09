from summarizer.summarize import generate_embedding
from search.chroma_store import search_summaries
from setup.logger import logger

def search_transcripts(query, top_k=5):
    """
    Search for summaries similar to the query text.
    
    Args:
        query (str): The text to search for.
        top_k (int): Number of results to return.
        
    Returns:
        List[Dict]: List of dictionaries containing search results.
        
    Examples:
        >>> results = search_transcripts("meeting about project timeline")
        >>> print(f"Found {len(results)} relevant results")
    """
    logger.info(f"Searching for: {query}")
    
    try:
        # Generate embedding for the query text
        query_embedding = generate_embedding(query)
        
        # Search using the embedding - use named parameter here
        results = search_summaries(query_embedding, top_k=top_k)  # Fix is here
        
        logger.info(f"Found {len(results)} results for query: {query}")
        return results
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return []
