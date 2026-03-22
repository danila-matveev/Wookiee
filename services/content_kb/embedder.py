"""
Gemini Embedding 2 client for images.

Uses google-generativeai SDK with gemini-embedding-2-preview model.
Embeds images natively (multimodal) with retry and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import time

import google.generativeai as genai

from . import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 8
BASE_BACKOFF = 15
MAX_BACKOFF = 300


class ImageEmbedder:
    """Gemini Embedding 2 for image embeddings."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ):
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.model = model or config.EMBEDDING_MODEL
        self.dimensions = dimensions or config.EMBEDDING_DIMENSIONS
        self._request_count = 0
        self._last_reset = time.time()

        genai.configure(api_key=self.api_key)
        logger.info("ImageEmbedder: model=%s, dims=%d", self.model, self.dimensions)

    async def _call_with_retry(self, func, *args, **kwargs):
        """Call with exponential backoff on 429."""
        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                    logger.warning("Rate limited (attempt %d/%d), waiting %ds...",
                                   attempt + 1, MAX_RETRIES, wait)
                    await asyncio.sleep(wait)
                    self._request_count = 0
                    self._last_reset = time.time()
                else:
                    raise
        raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded")

    async def _rate_limit(self):
        """Proactive rate limiter."""
        now = time.time()
        if now - self._last_reset > 60:
            self._request_count = 0
            self._last_reset = now

        if self._request_count >= 80:
            wait = 60 - (now - self._last_reset) + 1
            if wait > 0:
                logger.info("Rate limit pause: sleeping %.0fs", wait)
                await asyncio.sleep(wait)
                self._request_count = 0
                self._last_reset = time.time()

    async def embed_image(self, image_bytes: bytes, mime_type: str = "image/png") -> list[float]:
        """Embed a single image. Returns vector of `self.dimensions` floats."""
        await self._rate_limit()

        from google.generativeai import types
        part = types.BlobDict(mime_type=mime_type, data=image_bytes)

        result = await self._call_with_retry(
            genai.embed_content,
            model=f"models/{self.model}",
            content=part,
            output_dimensionality=self.dimensions,
        )
        self._request_count += 1
        return result["embedding"]

    async def embed_query(self, query: str) -> list[float]:
        """Embed a text query for searching against image embeddings."""
        await self._rate_limit()

        result = await self._call_with_retry(
            genai.embed_content,
            model=f"models/{self.model}",
            content=query,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=self.dimensions,
        )
        self._request_count += 1
        return result["embedding"]
