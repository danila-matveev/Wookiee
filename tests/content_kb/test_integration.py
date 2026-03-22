"""
Integration test: index a few real images → search → verify results.

Requires:
- YANDEX_DISK_TOKEN in .env
- GOOGLE_API_KEY in .env
- Migration 001 applied

Run: pytest tests/content_kb/test_integration.py -v -s
"""

import asyncio
import pytest
from services.content_kb.config import YANDEX_DISK_TOKEN, GOOGLE_API_KEY

pytestmark = pytest.mark.skipif(
    not YANDEX_DISK_TOKEN or not GOOGLE_API_KEY,
    reason="Requires YANDEX_DISK_TOKEN and GOOGLE_API_KEY",
)


@pytest.mark.asyncio
async def test_index_and_search_single_folder():
    """Index a small folder and search for images."""
    from services.content_kb.indexer import index_all
    from services.content_kb.search import search_content

    # Index just one small folder (few files)
    result = await index_all(
        root="/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777"
    )
    assert result["indexed"] > 0 or result["skipped"] > 0

    # Search
    search_result = await search_content(
        "каталожное фото нижнего белья",
        limit=3,
        include_preview=False,
    )
    assert search_result["total"] > 0
    assert search_result["results"][0]["similarity"] > 0.0


@pytest.mark.asyncio
async def test_search_with_filter():
    """Search with metadata filter."""
    from services.content_kb.search import search_content

    result = await search_content(
        "фото",
        model_name="Bella",
        color="black",
        limit=5,
        include_preview=False,
    )
    for item in result["results"]:
        assert item["model_name"].lower() == "bella"
        assert item["color"].lower() == "black"
