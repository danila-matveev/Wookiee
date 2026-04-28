"""FastAPI app factory for the Influencer CRM BFF.

Use create_app() — module-level `app = create_app()` is exposed for uvicorn
but tests should call create_app() directly so each test gets a fresh app.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from services.influencer_crm.config import LOG_LEVEL
from services.influencer_crm.etag import ETagMiddleware
from services.influencer_crm.routers import bloggers, briefs, health, integrations, metrics, products, promos, search, tags

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
    app.add_middleware(ETagMiddleware)
    app.include_router(health.router)
    app.include_router(bloggers.router)
    app.include_router(integrations.router)
    app.include_router(products.router)
    app.include_router(tags.router)
    app.include_router(promos.router)
    app.include_router(briefs.router)
    app.include_router(metrics.router)
    app.include_router(search.router)

    @app.exception_handler(IntegrityError)
    def _pg_integrity_handler(request, exc: IntegrityError):
        # Postgres unique-violation SQLSTATE = 23505
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "pgcode", None) if orig is not None else None
        if sqlstate == "23505":
            return JSONResponse(
                {"detail": "Unique constraint violation"},
                status_code=409,
            )
        return JSONResponse(
            {"detail": "Database integrity error"},
            status_code=500,
        )

    return app


app = create_app()
