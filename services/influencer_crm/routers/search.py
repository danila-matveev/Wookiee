from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.integration import IntegrationOut
from shared.data_layer.influencer_crm import bloggers as bloggers_repo

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
    int_rows = session.execute(
        text(
            "SELECT id, blogger_id, marketer_id, brief_id, "
            "       publish_date, channel, ad_format, marketplace, "
            "       stage, outcome, is_barter, "
            "       cost_placement, cost_delivery, cost_goods, total_cost, "
            "       erid, fact_views, fact_orders, fact_revenue, "
            "       created_at, updated_at "
            "FROM crm.integrations "
            "WHERE archived_at IS NULL AND ("
            "    COALESCE(notes, '') ILIKE '%' || :q || '%' "
            " OR COALESCE(post_content, '') ILIKE '%' || :q || '%'"
            ") ORDER BY updated_at DESC LIMIT :limit"
        ),
        {"q": q, "limit": limit},
    ).mappings().all()
    integrations = [IntegrationOut(**dict(r)) for r in int_rows]
    return {"bloggers": bloggers, "integrations": integrations}
