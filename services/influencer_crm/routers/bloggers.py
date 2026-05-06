"""GET /bloggers, GET /bloggers/{id}, POST /bloggers, PATCH /bloggers/{id}."""
from __future__ import annotations

import logging  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.blogger import (
    BloggerCreate,
    BloggerDetailOut,
    BloggerOut,
    BloggerSummaryPage,
    BloggerUpdate,
)
from shared.data_layer.influencer_crm import bloggers as repo

router = APIRouter(
    prefix="/bloggers",
    tags=["bloggers"],
    dependencies=[Depends(verify_api_key)],
)

logger = logging.getLogger("influencer_crm.bloggers")


@router.get("", response_model=Page[BloggerOut])
def list_bloggers(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    marketer_id: int | None = None,
    q: str | None = None,
    channel: str | None = Query(default=None),
) -> Page[BloggerOut]:
    items, next_cursor = repo.list_bloggers(
        session, limit=limit, cursor=cursor,
        status=status_filter, marketer_id=marketer_id, q=q,
        channel=channel,
    )
    return Page[BloggerOut](items=items, next_cursor=next_cursor)


@router.get("/summary", response_model=BloggerSummaryPage)
def get_bloggers_summary(
    status: str | None = None,
    q: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=200, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> BloggerSummaryPage:
    """Enriched blogger list for table view with channels and aggregate metrics."""
    from shared.data_layer.influencer_crm import bloggers as dl

    items, total = dl.list_bloggers_summary(
        session, limit=limit, offset=offset, status=status, q=q, channel=channel
    )
    return BloggerSummaryPage(items=items, total=total)


@router.get("/{blogger_id}", response_model=BloggerDetailOut)
def get_blogger(
    blogger_id: int,
    session: Session = Depends(get_session),
) -> BloggerDetailOut:
    blogger = repo.get_blogger(session, blogger_id)
    if blogger is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blogger not found")
    return blogger


@router.post("", response_model=BloggerOut, status_code=status.HTTP_201_CREATED)
def create_blogger(
    payload: BloggerCreate,
    session: Session = Depends(get_session),
) -> BloggerOut:
    new_id = repo.create_blogger(session, **payload.model_dump(exclude_unset=True))
    created = repo.get_blogger(session, new_id)
    if created is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")
    return BloggerOut.model_validate(created.model_dump())


@router.patch("/{blogger_id}", response_model=BloggerOut)
def patch_blogger(
    blogger_id: int,
    payload: BloggerUpdate,
    session: Session = Depends(get_session),
) -> BloggerOut:
    fields = payload.model_dump(exclude_unset=True)
    repo.update_blogger(session, blogger_id, fields)
    updated = repo.get_blogger(session, blogger_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blogger not found")
    return BloggerOut.model_validate(updated.model_dump())
