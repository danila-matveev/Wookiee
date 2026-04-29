"""ETag middleware for GET endpoints (excluding /health).

Computes hash over the response body and adds it as `ETag`. Honors
`If-None-Match` for 304 responses.
"""
from __future__ import annotations

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ETagMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {
        "/health", "/openapi.json", "/docs", "/redoc",
        # Same set under the /api/* alias (production layout).
        "/api/health", "/api/openapi.json", "/api/docs", "/api/redoc",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "GET" or request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        response = await call_next(request)
        if response.status_code != 200:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})

        new_response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        new_response.headers["ETag"] = etag
        return new_response
