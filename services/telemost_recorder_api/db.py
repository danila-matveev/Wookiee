"""Asyncpg pool management for the API. Singleton pattern, lifespan-managed."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import asyncpg

from services.telemost_recorder_api.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    """Lazy-init the asyncio lock so we don't bind to a non-existent event loop at import time."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_pool() -> asyncpg.Pool:
    """Return the singleton pool, creating it lazily on first call."""
    global _pool
    async with _get_lock():
        if _pool is None or _pool._closed:
            logger.info("Creating asyncpg pool")
            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
        return _pool


async def close_pool() -> None:
    """Close the pool if open. Idempotent."""
    global _pool
    async with _get_lock():
        if _pool is not None and not _pool._closed:
            await _pool.close()
        _pool = None
