"""FastAPI factory for telemost_recorder_api.

Lifespan:
- Startup: open DB pool, start recorder + postprocess worker tasks.
- Shutdown: cancel both workers, close DB pool.

Future tasks will add: bot avatar setup, user sync.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from services.telemost_recorder_api import internal_routes
from services.telemost_recorder_api.config import (
    LOG_LEVEL,
    TELEGRAM_TIMEOUT_SECONDS,
    TELEMOST_PUBLIC_URL,
    TELEMOST_WEBHOOK_SECRET,
)
from services.telemost_recorder_api.db import close_pool, get_pool
from services.telemost_recorder_api.docker_client import docker_ping
from services.telemost_recorder_api.error_alerts import install_telegram_alerts
from services.telemost_recorder_api.routes import health, telegram
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    close_client,
    init_client,
    tg_call,
)
from services.telemost_recorder_api.workers.cleanup_worker import (
    run_forever as cleanup_loop,
)
from services.telemost_recorder_api.workers.postprocess_worker import (
    run_forever as postprocess_loop,
)
from services.telemost_recorder_api.workers.recorder_worker import (
    run_forever as recorder_loop,
)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)
install_telegram_alerts(service="telemost-api")


_WORKER_BACKOFF_SECONDS = 5

# Columns that must exist on telemost.meetings for the API workers to function.
# Derived from migrations 001 (base table) + 003 (deleted_at) + 004 (notion_*).
# Keep in sync with services/telemost_recorder_api/migrations/*.sql so missing
# migrations crash startup loudly instead of failing in worker SQL later.
_EXPECTED_MEETINGS_COLUMNS = {
    "id",
    "source",
    "source_event_id",
    "triggered_by",
    "meeting_url",
    "title",
    "organizer_id",
    "invitees",
    "scheduled_at",
    "started_at",
    "ended_at",
    "duration_seconds",
    "status",
    "error",
    "audio_path",
    "audio_expires_at",
    "raw_segments",
    "processed_paragraphs",
    "speakers_map",
    "summary",
    "tags",
    "notified_at",
    "created_at",
    "updated_at",
    "deleted_at",
    "notion_page_id",
    "notion_page_url",
}


async def _validate_schema() -> None:
    """Fail fast if telemost.meetings is missing expected columns.

    Runs once on lifespan startup right after the pool is opened. If a
    deploy lands without running the latest migration we want to crash the
    container immediately rather than 30 minutes later inside a worker
    INSERT that mentions a non-existent column.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'telemost' AND table_name = 'meetings'
            """,
        )
    actual = {r["column_name"] for r in rows}
    missing = _EXPECTED_MEETINGS_COLUMNS - actual
    if missing:
        raise RuntimeError(
            f"telemost.meetings is missing expected columns: {sorted(missing)}. "
            "Run database migrations."
        )


async def _supervised(name: str, coro_factory) -> None:
    """Run worker loop forever; if it crashes, log + restart after backoff.

    Each `run_forever()` already swallows per-iteration errors, but if the
    outer loop itself dies (network/DB transient) the worker would silently
    stay dead until the next container restart. This wrapper keeps it alive.
    """
    while True:
        try:
            await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Worker %s crashed; restarting in %ss", name, _WORKER_BACKOFF_SECONDS)
            await asyncio.sleep(_WORKER_BACKOFF_SECONDS)


async def _ensure_telegram_webhook() -> None:
    """Re-register Telegram webhook on startup so a container restart
    can't leave the bot deaf. Idempotent on Telegram's side. Silently no-op
    if TELEMOST_PUBLIC_URL is empty (dev/tests)."""
    if not TELEMOST_PUBLIC_URL:
        logger.info("TELEMOST_PUBLIC_URL not set, skipping webhook registration")
        return
    target = f"{TELEMOST_PUBLIC_URL}/telegram/webhook"
    try:
        await tg_call(
            "setWebhook",
            url=target,
            secret_token=TELEMOST_WEBHOOK_SECRET,
            allowed_updates=["message", "edited_message", "chat_member", "callback_query"],
        )
        logger.info("Telegram webhook registered: %s", target)
    except (TelegramAPIError, httpx.HTTPError) as e:
        logger.exception("Failed to register Telegram webhook (%s): %s", target, e)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    # Initialise the singleton httpx.AsyncClient before anything that touches
    # the Telegram API (including the webhook re-registration below and the
    # workers spawned further down).
    init_client(timeout=TELEGRAM_TIMEOUT_SECONDS)
    await get_pool()
    await _validate_schema()
    if not await docker_ping():
        # Don't block startup — supervised worker logs will keep flagging,
        # and Docker's restart-policy can recycle the container if needed.
        # But scream loud now so the operator sees it on first boot.
        logger.critical(
            "docker.sock unreachable on startup; recorder spawns will fail"
        )
    await _ensure_telegram_webhook()
    recorder_task = asyncio.create_task(
        _supervised("recorder_worker", recorder_loop), name="recorder_worker"
    )
    postprocess_task = asyncio.create_task(
        _supervised("postprocess_worker", postprocess_loop), name="postprocess_worker"
    )
    cleanup_task = asyncio.create_task(
        _supervised("cleanup_worker", cleanup_loop), name="cleanup_worker"
    )
    try:
        yield
    finally:
        logger.info("telemost-recorder-api shutting down")
        for task in (recorder_task, postprocess_task, cleanup_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await close_pool()
        # Close the Telegram client last so that any final shutdown calls
        # from worker cancellation paths still have a live client.
        await close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telemost Recorder API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.include_router(health.router)
    app.include_router(telegram.router)
    app.include_router(internal_routes.router)
    return app
