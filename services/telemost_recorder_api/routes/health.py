"""GET /health — DB ping + docker.sock liveness + queue snapshot.

Returns 200 only if BOTH docker daemon and DB are reachable. If either is
unhealthy, the endpoint returns HTTP 503 with a structured payload so
container orchestrators (and humans) see the failure immediately.

Without the docker check the API would happily start "healthy" and only
fail when the first recorder spawn arrived — by which point the user is
already waiting on a meeting.

Docker ping (up to 5s) and DB check (up to 2s) run in parallel via
asyncio.gather, so worst-case latency is max(5s, 2s) = 5s instead of
the previous sequential 8s — well under typical k8s/docker healthcheck
timeouts. The DB check is wrapped in asyncio.wait_for so a saturated
pool can't hang the endpoint indefinitely on pool.acquire().
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.docker_client import docker_ping

logger = logging.getLogger(__name__)
router = APIRouter()


async def _check_db() -> tuple[bool, dict, str | None]:
    """Run DB liveness + queue snapshot under a single connection.

    Wrapped in asyncio.wait_for(timeout=2.0) so a hung pool.acquire()
    (pool exhausted, network stalled) can't block /health forever.
    Returns (ok, checks_payload, error_message).

    Using asyncio.wait_for around a helper coroutine instead of
    `async with asyncio.timeout(...)` for Python 3.9 compatibility on
    dev machines; behaviour is equivalent in production (3.11+).
    """
    started = time.perf_counter()

    async def _do_check() -> dict:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            queue_size = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'queued'"
            ) or 0
            recording_count = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'recording'"
            ) or 0
            return {
                "queue_size": queue_size,
                "recording_count": recording_count,
            }

    try:
        result = await asyncio.wait_for(_do_check(), timeout=2.0)
        db_ping_ms = int((time.perf_counter() - started) * 1000)
        return True, {"db_ping_ms": db_ping_ms, **result}, None
    except asyncio.TimeoutError:
        db_ping_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("DB health check timed out after %sms", db_ping_ms)
        return False, {
            "db_ping_ms": db_ping_ms,
            "queue_size": 0,
            "recording_count": 0,
        }, "db check timed out"
    except Exception as exc:  # noqa: BLE001
        db_ping_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("DB health check failed: %s", exc)
        return False, {
            "db_ping_ms": db_ping_ms,
            "queue_size": 0,
            "recording_count": 0,
        }, str(exc)


@router.get("/health")
async def health() -> dict:
    docker_ok, (db_ok, db_checks, db_error) = await asyncio.gather(
        docker_ping(),
        _check_db(),
    )

    if not (docker_ok and db_ok):
        payload = {
            "status": "unhealthy",
            "docker": "ok" if docker_ok else "unhealthy",
            "db": "ok" if db_ok else "unhealthy",
            "checks": db_checks,
        }
        if db_error is not None:
            payload["error"] = db_error
        raise HTTPException(status_code=503, detail=payload)

    overall = "degraded" if db_checks["db_ping_ms"] > 1000 else "ok"
    return {
        "status": overall,
        "docker": "ok",
        "db": "ok",
        "checks": db_checks,
    }
