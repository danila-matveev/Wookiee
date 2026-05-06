"""FastAPI dependency injection: auth, DB session, pagination."""
from __future__ import annotations

from typing import Iterator, Optional

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm import config
from shared.data_layer.influencer_crm._engine import session_factory

_jwks_client: Optional[PyJWKClient] = None

def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not config.SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL not set in .env")
        _jwks_client = PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Accept Supabase Bearer JWT (Hub SPA) or static X-API-Key (server scripts)."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        _verify_supabase_jwt(token)
        return
    if x_api_key is not None:
        if x_api_key != config.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid X-API-Key",
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="X-API-Key header required",
    )


def _verify_supabase_jwt(token: str) -> None:
    if not config.SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bearer auth not configured (SUPABASE_URL missing)",
        )
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256", "HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid token: {exc}")


def get_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session for one request."""
    with session_factory() as s:
        yield s
