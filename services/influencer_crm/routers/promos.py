from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.promo import PromoCodeOut, SubstituteArticleOut
from shared.data_layer.influencer_crm import promos as repo

router = APIRouter(
    tags=["promos"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/substitute-articles", response_model=Page[SubstituteArticleOut])
def list_substitute_articles(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status: str | None = None,
) -> Page[SubstituteArticleOut]:
    items, nxt = repo.list_substitute_articles(session, limit=limit, cursor=cursor, status=status)
    return Page[SubstituteArticleOut](items=items, next_cursor=nxt)


@router.get("/promo-codes", response_model=Page[PromoCodeOut])
def list_promo_codes(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status: str | None = None,
) -> Page[PromoCodeOut]:
    items, nxt = repo.list_promo_codes(session, limit=limit, cursor=cursor, status=status)
    return Page[PromoCodeOut](items=items, next_cursor=nxt)
