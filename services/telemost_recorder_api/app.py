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
    TELEMOST_PUBLIC_URL,
    TELEMOST_WEBHOOK_SECRET,
)
from services.telemost_recorder_api.db import close_pool, get_pool
from services.telemost_recorder_api.error_alerts import install_telegram_alerts
from services.telemost_recorder_api.routes import health, telegram
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_call,
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
            allowed_updates=["message", "edited_message", "chat_member"],
        )
        logger.info("Telegram webhook registered: %s", target)
    except (TelegramAPIError, httpx.HTTPError) as e:
        logger.exception("Failed to register Telegram webhook (%s): %s", target, e)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    await get_pool()
    await _ensure_telegram_webhook()
    recorder_task = asyncio.create_task(
        _supervised("recorder_worker", recorder_loop), name="recorder_worker"
    )
    postprocess_task = asyncio.create_task(
        _supervised("postprocess_worker", postprocess_loop), name="postprocess_worker"
    )
    try:
        yield
    finally:
        logger.info("telemost-recorder-api shutting down")
        for task in (recorder_task, postprocess_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await close_pool()


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
