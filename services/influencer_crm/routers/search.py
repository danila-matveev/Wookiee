from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from shared.data_layer.influencer_crm import bloggers as bloggers_repo
from shared.data_layer.influencer_crm import integrations as integrations_repo

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict:
    bloggers = bloggers_repo.search_bloggers(session, q, limit)
    integrations = integrations_repo.search_integrations(session, q, limit)
    return {"bloggers": bloggers, "integrations": integrations}
