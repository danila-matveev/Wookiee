"""
Content search: embed text query → pgvector similarity search → preview URLs.
"""

from __future__ import annotations

import asyncio
import logging

from .embedder import ImageEmbedder
from .store import ContentStore
from .yadisk_client import YaDiskClient

logger = logging.getLogger(__name__)

# Singletons (initialized on first use)
_embedder: ImageEmbedder | None = None
_store: ContentStore | None = None
_yadisk: YaDiskClient | None = None


def _get_embedder() -> ImageEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = ImageEmbedder()
    return _embedder


def _get_store() -> ContentStore:
    global _store
    if _store is None:
        _store = ContentStore()
    return _store


def _get_yadisk() -> YaDiskClient:
    global _yadisk
    if _yadisk is None:
        _yadisk = YaDiskClient()
    return _yadisk


async def search_content(
    query: str,
    limit: int = 10,
    model_name: str | None = None,
    color: str | None = None,
    category: str | None = None,
    sku: str | None = None,
    min_similarity: float = 0.3,
    include_preview: bool = True,
) -> dict:
    """Search content by text query + metadata filters."""
    embedder = _get_embedder()
    store = _get_store()

    query_embedding = await embedder.embed_query(query)

    results = store.search(
        query_embedding=query_embedding,
        limit=limit,
        model_name=model_name,
        color=color,
        category=category,
        sku=sku,
        min_similarity=min_similarity,
    )

    items = []
    for r in results:
        item = {
            "disk_path": r.disk_path,
            "file_name": r.file_name,
            "similarity": round(r.similarity, 4),
            "model_name": r.model_name,
            "color": r.color,
            "category": r.content_category,
            "sku": r.sku,
        }

        if include_preview:
            item["preview_url"] = None

        items.append(item)

    # Generate preview URLs in parallel
    if include_preview and items:
        yadisk_client = _get_yadisk()
        preview_tasks = [
            asyncio.to_thread(yadisk_client.get_preview_url, item["disk_path"])
            for item in items
        ]
        previews = await asyncio.gather(*preview_tasks, return_exceptions=True)
        for item, preview in zip(items, previews):
            if isinstance(preview, str):
                item["preview_url"] = preview

    return {"total": len(items), "results": items}
