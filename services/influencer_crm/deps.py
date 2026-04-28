"""FastAPI dependency injection: auth, DB session, pagination."""
from __future__ import annotations

from typing import Iterator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm.config import API_KEY
from shared.data_layer.influencer_crm._engine import session_factory


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-API-Key header required",
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-API-Key",
        )


def get_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session for one request."""
    with session_factory() as s:
        yield s
