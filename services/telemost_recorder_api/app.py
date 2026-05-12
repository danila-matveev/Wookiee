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

from fastapi import FastAPI

from services.telemost_recorder_api import internal_routes
from services.telemost_recorder_api.config import LOG_LEVEL
from services.telemost_recorder_api.db import close_pool, get_pool
from services.telemost_recorder_api.error_alerts import install_telegram_alerts
from services.telemost_recorder_api.routes import health, telegram
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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    await get_pool()
    recorder_task = asyncio.create_task(recorder_loop(), name="recorder_worker")
    postprocess_task = asyncio.create_task(
        postprocess_loop(), name="postprocess_worker"
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
