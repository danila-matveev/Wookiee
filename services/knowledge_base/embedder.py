"""
Gemini Embedding 2 client.

Uses google-generativeai SDK with gemini-embedding-2-preview model.
Supports Matryoshka dimension truncation and batch embedding.
Includes retry with exponential backoff for rate limits.
"""

import asyncio
import logging
import time
from typing import Optional

import google.generativeai as genai

from . import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 8
BASE_BACKOFF = 15  # seconds
MAX_BACKOFF = 300  # cap at 5 minutes


class GeminiEmbedder:
    """Async wrapper around Gemini Embedding API with rate limit handling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        max_concurrent: Optional[int] = None,
    ):
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.model = model or config.EMBEDDING_MODEL
        self.dimensions = dimensions or config.EMBEDDING_DIMENSIONS
        self._semaphore = asyncio.Semaphore(
            max_concurrent or config.EMBED_MAX_CONCURRENT
        )
        self._request_count = 0
        self._last_reset = time.time()

        genai.configure(api_key=self.api_key)
        logger.info(
            "GeminiEmbedder initialized: model=%s, dims=%d",
            self.model, self.dimensions,
        )

    async def _call_with_retry(self, func, *args, **kwargs):
        """Call function with exponential backoff on 429 errors."""
        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                    logger.warning(
                        "Rate limited (attempt %d/%d), waiting %ds...",
                        attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    self._request_count = 0
                    self._last_reset = time.time()
                else:
                    raise
        raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded for embedding")

    async def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        """Embed a single text string."""
        async with self._semaphore:
            await self._rate_limit()
            result = await self._call_with_retry(
                genai.embed_content,
                model=f"models/{self.model}",
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimensions,
            )
            self._request_count += 1
            return result["embedding"]

    async def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: Optional[int] = None,
    ) -> list[list[float]]:
        """Embed a batch of texts with rate limiting and retry."""
        batch_size = batch_size or config.EMBED_BATCH_SIZE
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            async with self._semaphore:
                await self._rate_limit()
                result = await self._call_with_retry(
                    genai.embed_content,
                    model=f"models/{self.model}",
                    content=batch,
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                )
                self._request_count += len(batch)
                all_embeddings.extend(result["embedding"])

            logger.info(
                "Embedded %d/%d chunks",
                min(i + batch_size, len(texts)), len(texts),
            )

            # Delay between batches to stay within TPM limits
            if i + batch_size < len(texts):
                delay = getattr(config, 'EMBED_BATCH_DELAY', 2.0)
                await asyncio.sleep(delay)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a search query (uses RETRIEVAL_QUERY task type)."""
        return await self.embed(query, task_type="RETRIEVAL_QUERY")

    async def _rate_limit(self):
        """Proactive rate limiter: pause before hitting limits."""
        now = time.time()
        if now - self._last_reset > 60:
            self._request_count = 0
            self._last_reset = now

        # Free tier: ~100 RPM for embedding, be conservative
        if self._request_count >= 80:
            wait = 60 - (now - self._last_reset) + 1
            if wait > 0:
                logger.info("Rate limit pause: sleeping %.0fs (sent %d reqs)",
                            wait, self._request_count)
                await asyncio.sleep(wait)
                self._request_count = 0
                self._last_reset = time.time()
