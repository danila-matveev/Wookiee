"""FastAPI dependency injection: auth, DB session, pagination."""
from __future__ import annotations

from typing import Iterator, Optional

import jwt
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm import config
from shared.data_layer.influencer_crm._engine import session_factory


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
    if not config.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bearer auth not configured on server (SUPABASE_JWT_SECRET missing)",
        )
    try:
        jwt.decode(
            token,
            config.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
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
