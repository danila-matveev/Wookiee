"""Tests for the asyncpg pool. These actually hit Supabase — they require working .env."""
from __future__ import annotations

import pytest

from services.telemost_recorder_api.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_pool_singleton():
    pool1 = await get_pool()
    pool2 = await get_pool()
    assert pool1 is pool2
    await close_pool()


@pytest.mark.asyncio
async def test_pool_can_query():
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
    finally:
        await close_pool()


@pytest.mark.asyncio
async def test_pool_recreated_after_close():
    pool1 = await get_pool()
    await close_pool()
    pool2 = await get_pool()
    assert pool1 is not pool2  # new instance after close
    await close_pool()


@pytest.mark.asyncio
async def test_close_pool_is_idempotent():
    await get_pool()
    await close_pool()
    await close_pool()  # should not raise
