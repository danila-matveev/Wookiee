"""Read/write queries for crm.integrations + related M:N."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.integration import (
    IntegrationDetailOut,
    IntegrationOut,
    IntegrationPostOut,
    IntegrationSubstituteOut,
)


_LIST_BASE = """
SELECT i.id, i.blogger_id, i.marketer_id, i.brief_id,
       i.publish_date, i.channel, i.ad_format, i.marketplace,
       i.stage, i.outcome, i.is_barter,
       i.cost_placement, i.cost_delivery, i.cost_goods, i.total_cost,
       i.erid, i.fact_views, i.fact_orders, i.fact_revenue,
       i.created_at, i.updated_at
FROM crm.integrations i
WHERE i.archived_at IS NULL
"""


def list_integrations(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
    stage_in: list[str] | None = None,
    marketplace: str | None = None,
    marketer_id: int | None = None,
    blogger_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[IntegrationOut], str | None]:
    params: dict[str, Any] = {"limit": limit + 1}
    where: list[str] = []

    if stage_in:
        where.append("AND i.stage = ANY(:stage_in)")
        params["stage_in"] = stage_in
    if marketplace:
        where.append("AND i.marketplace = :marketplace")
        params["marketplace"] = marketplace
    if marketer_id is not None:
        where.append("AND i.marketer_id = :marketer_id")
        params["marketer_id"] = marketer_id
    if blogger_id is not None:
        where.append("AND i.blogger_id = :blogger_id")
        params["blogger_id"] = blogger_id
    if date_from:
        where.append("AND i.publish_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("AND i.publish_date <= :date_to")
        params["date_to"] = date_to

    decoded = decode_cursor(cursor)
    if decoded is not None:
        cursor_ts, cursor_id = decoded
        where.append("AND (i.updated_at, i.id) < (:cursor_ts, :cursor_id)")
        params["cursor_ts"] = cursor_ts
        params["cursor_id"] = cursor_id

    sql = (
        _LIST_BASE
        + " " + " ".join(where)
        + " ORDER BY i.updated_at DESC, i.id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [IntegrationOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["updated_at"], rows[-1]["id"])
        if has_more and rows
        else None
    )
    return items, next_cursor


_DETAIL_SQL = """
SELECT i.*, b.display_handle AS blogger_handle, m.name AS marketer_name
FROM crm.integrations i
JOIN crm.bloggers b   ON b.id = i.blogger_id
JOIN crm.marketers m  ON m.id = i.marketer_id
WHERE i.id = :id AND i.archived_at IS NULL
"""

_SUBS_SQL = """
SELECT isa.substitute_article_id, sa.code, sa.artikul_id,
       isa.display_order, isa.tracking_url
FROM crm.integration_substitute_articles isa
JOIN crm.substitute_articles sa ON sa.id = isa.substitute_article_id
WHERE isa.integration_id = :integration_id
ORDER BY isa.display_order, isa.substitute_article_id
"""

_POSTS_SQL = """
SELECT id, post_url, posted_at, fact_views, fact_clicks
FROM crm.integration_posts
WHERE integration_id = :integration_id
ORDER BY posted_at DESC NULLS LAST, id DESC
"""


def get_integration(session: Session, integration_id: int) -> IntegrationDetailOut | None:
    head = session.execute(text(_DETAIL_SQL), {"id": integration_id}).mappings().first()
    if head is None:
        return None
    subs = session.execute(text(_SUBS_SQL), {"integration_id": integration_id}).mappings().all()
    posts = session.execute(text(_POSTS_SQL), {"integration_id": integration_id}).mappings().all()
    payload = dict(head)
    payload["substitutes"] = [IntegrationSubstituteOut(**dict(s)) for s in subs]
    payload["posts"] = [IntegrationPostOut(**dict(p)) for p in posts]
    return IntegrationDetailOut(**payload)


_INSERT_SQL = """
INSERT INTO crm.integrations (
    blogger_id, marketer_id, publish_date, channel, ad_format, marketplace,
    stage, is_barter, cost_placement, cost_delivery, cost_goods, erid, notes
) VALUES (
    :blogger_id, :marketer_id, :publish_date, :channel, :ad_format, :marketplace,
    :stage, :is_barter, :cost_placement, :cost_delivery, :cost_goods, :erid, :notes
) RETURNING id
"""


def create_integration(session: Session, **fields: Any) -> int:
    payload = {k: fields.get(k) for k in (
        "blogger_id", "marketer_id", "publish_date", "channel", "ad_format",
        "marketplace", "stage", "is_barter", "cost_placement", "cost_delivery",
        "cost_goods", "erid", "notes",
    )}
    payload["stage"] = payload["stage"] or "lead"
    payload["is_barter"] = bool(payload["is_barter"])
    return int(session.execute(text(_INSERT_SQL), payload).scalar_one())


_UPDATABLE = {
    "blogger_id", "marketer_id", "publish_date", "channel", "ad_format",
    "marketplace", "stage", "outcome", "is_barter",
    "cost_placement", "cost_delivery", "cost_goods", "erid", "notes",
    "fact_views", "fact_orders", "fact_revenue",
}


def update_integration(
    session: Session, integration_id: int, fields: dict[str, Any]
) -> None:
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not fields:
        return
    # k comes from the _UPDATABLE whitelist above — not user-controlled.
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = (
        f"UPDATE crm.integrations SET {set_clause}, updated_at = now() "
        f"WHERE id = :id AND archived_at IS NULL"
    )
    session.execute(text(sql), {**fields, "id": integration_id})


def transition_stage(
    session: Session, integration_id: int, *, target_stage: str, note: str | None = None
) -> None:
    """Stage column update — trigger writes integration_stage_history row."""
    update_integration(session, integration_id, {"stage": target_stage})
    if note:
        session.execute(
            text(
                "UPDATE crm.integration_stage_history "
                "SET comment = :note WHERE integration_id = :id "
                "  AND id = (SELECT MAX(id) FROM crm.integration_stage_history "
                "            WHERE integration_id = :id)"
            ),
            {"note": note, "id": integration_id},
        )
