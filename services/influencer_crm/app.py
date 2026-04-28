"""FastAPI app factory for the Influencer CRM BFF.

Use create_app() — module-level `app = create_app()` is exposed for uvicorn
but tests should call create_app() directly so each test gets a fresh app.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from services.influencer_crm.config import LOG_LEVEL
from services.influencer_crm.routers import bloggers, health, integrations

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Influencer CRM API",
        description="BFF for the React frontend (P4). All endpoints "
                    "except /health require X-API-Key.",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(bloggers.router)
    app.include_router(integrations.router)
    return app


app = create_app()
