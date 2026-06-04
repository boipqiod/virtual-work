"""
Memory Retrieval — Finds relevant past context for a given topic.
Simple keyword-based for now. Can be upgraded to embeddings later.
"""

from memory.store import MemoryStore


def get_relevant_context(memory: MemoryStore, current_text: str, limit: int = 30) -> str:
    """
    Get context relevant to the current message.
    For now, just returns recent messages. 
    Future: keyword matching or embedding-based retrieval.
    """
    # Simple approach: return the full recent context
    # The MemoryStore.get_context() already does this well enough
    return memory.get_context()
