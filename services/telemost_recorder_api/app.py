"""FastAPI factory for telemost_recorder_api.

Lifespan:
- Startup: open DB pool (warming the singleton lock too).
- Shutdown: close DB pool.

Future tasks will add: bot avatar setup, recorder/postprocess workers, user sync.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.telemost_recorder_api.config import LOG_LEVEL
from services.telemost_recorder_api.db import close_pool, get_pool
from services.telemost_recorder_api.routes import health

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    await get_pool()
    try:
        yield
    finally:
        logger.info("telemost-recorder-api shutting down")
        await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telemost Recorder API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.include_router(health.router)
    return app
