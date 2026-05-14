"""Shared auth helpers for analytics_api endpoints.

Two auth modes accepted on every protected endpoint:
1. Bearer JWT — Hub frontend session token, validated against Supabase JWKS.
2. X-Api-Key  — server-to-server / cron / manual smoke-tests.

Extracted into its own module so both `app.py` (РНП endpoints) and
`marketing.py` (sync triggers) can use it without a circular import
(`app.py` imports `marketing.router`, so `marketing.py` cannot import
`app.py`).
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

ANALYTICS_API_KEY = os.getenv("ANALYTICS_API_KEY", "")
SUPABASE_URL      = os.getenv("SUPABASE_URL", "")

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL not set in .env")
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _verify_supabase_jwt(token: str) -> None:
    if not SUPABASE_URL:
        raise HTTPException(403, "Bearer auth not configured (SUPABASE_URL missing)")
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256", "HS256"], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(403, f"Invalid token: {exc}")


def verify_auth(
    x_api_key: str | None = None,
    authorization: str | None = None,
) -> None:
    """Bearer JWT (Hub) OR X-Api-Key (cron) — either is sufficient."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        _verify_supabase_jwt(token)
        return
    if x_api_key is not None:
        if not ANALYTICS_API_KEY:
            raise HTTPException(500, "ANALYTICS_API_KEY not configured")
        if x_api_key != ANALYTICS_API_KEY:
            raise HTTPException(403, "Invalid API key")
        return
    raise HTTPException(403, "Authorization required: Bearer token or X-Api-Key header")


def require_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency wrapper around verify_auth."""
    verify_auth(x_api_key, authorization)
