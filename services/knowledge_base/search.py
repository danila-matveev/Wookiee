"""
Search module — embeds query and searches pgvector store.
"""

import logging
from dataclasses import asdict
from typing import Optional

from .embedder import GeminiEmbedder
from .store import KnowledgeStore, SearchResult

logger = logging.getLogger(__name__)

# Singleton instances (initialized on first use)
_embedder: Optional[GeminiEmbedder] = None
_store: Optional[KnowledgeStore] = None


def _get_embedder() -> GeminiEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = GeminiEmbedder()
    return _embedder


def _get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


async def search_knowledge(
    query: str,
    limit: int = 5,
    module: Optional[str] = None,
    content_type: Optional[str] = None,
    min_score: float = 0.5,
) -> list[dict]:
    """
    Search the knowledge base.

    Args:
        query: Search query in natural language
        limit: Max results to return
        module: Optional filter by module ("1"-"8" or "processes")
        content_type: Optional filter ("theory", "template", "example")
        min_score: Minimum similarity score (0-1)

    Returns:
        List of result dicts with text, score, and metadata.
    """
    embedder = _get_embedder()
    store = _get_store()

    # Embed query with RETRIEVAL_QUERY task type
    query_embedding = await embedder.embed_query(query)

    # Search pgvector
    results = store.search(
        query_embedding=query_embedding,
        limit=limit,
        module=module,
        content_type=content_type,
        min_similarity=min_score,
    )

    return [
        {
            "text": r.content,
            "score": round(r.similarity, 4),
            "module": r.module,
            "file_name": r.file_name,
            "file_type": r.file_type,
            "content_type": r.content_type,
            "chunk_index": r.chunk_index,
            "source_path": r.source_path,
        }
        for r in results
    ]
