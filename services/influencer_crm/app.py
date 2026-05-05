"""FastAPI app factory for the Influencer CRM BFF.

Use create_app() — module-level `app = create_app()` is exposed for uvicorn
but tests should call create_app() directly so each test gets a fresh app.

Routing layout in production:
- /api/*  — JSON API (SPA calls these via VITE_API_BASE_URL=/api).
- /*     — pre-built React SPA from /app/ui_dist (when present in image).
- /<router>/* (no /api prefix) — kept registered for test/CLI clients
  that already call e.g. client.get("/bloggers").

The SPA-fallback wrapper around StaticFiles ensures deep-link refreshes
(e.g. /bloggers/123) return index.html so the SPA router can take over.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.influencer_crm.config import LOG_LEVEL
from services.influencer_crm.etag import ETagMiddleware
from services.influencer_crm.routers import (
    bloggers,
    briefs,
    health,
    integrations,
    metrics,
    ops,
    products,
    promos,
    search,
    tags,
)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

UI_DIST_DIR = Path("/app/ui_dist")  # populated by deploy/Dockerfile.influencer_crm_api


class SPAStaticFiles(StaticFiles):
    """StaticFiles that returns index.html for unknown paths so SPA deep
    links survive a refresh."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as e:
            if e.status_code == 404:
                response = await super().get_response("index.html", scope)
            else:
                raise
        # index.html must never be cached — content-hashed assets can be.
        if path in ("", "index.html") or not path.startswith("assets/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Influencer CRM API",
        description="BFF for the React frontend (P4). All endpoints "
                    "except /health require X-API-Key.",
        version="0.1.0",
    )
    app.add_middleware(ETagMiddleware)

    api_routers = [
        health,
        bloggers,
        integrations,
        products,
        tags,
        promos,
        briefs,
        metrics,
        search,
        ops,
    ]
    # ALL endpoints live under /api so the SPA can claim /, /bloggers/123, etc.
    # Tests use the same /api prefix.
    for module in api_routers:
        app.include_router(module.router, prefix="/api")

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

    # Mount SPA static last — routers above win for any /api/* and /<router>/* path,
    # SPA serves everything else (index.html, /assets/*, deep links).
    if UI_DIST_DIR.exists():
        app.mount("/", SPAStaticFiles(directory=str(UI_DIST_DIR), html=True), name="ui")

    return app


app = create_app()
