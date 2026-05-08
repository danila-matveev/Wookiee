"""GET /health — DB ping + queue snapshot."""
from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.telemost_recorder_api.db import get_pool

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    started = time.perf_counter()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            queue_size = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'queued'"
            ) or 0
            recording_count = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'recording'"
            ) or 0
    except Exception as exc:
        return JSONResponse(
            {"status": "down", "error": str(exc)},
            status_code=503,
        )
    db_ping_ms = int((time.perf_counter() - started) * 1000)
    status = "degraded" if db_ping_ms > 1000 else "ok"
    return JSONResponse({
        "status": status,
        "checks": {
            "db_ping_ms": db_ping_ms,
            "queue_size": queue_size,
            "recording_count": recording_count,
        },
    })
