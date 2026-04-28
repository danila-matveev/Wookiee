"""Read+write queries for crm.bloggers + crm.blogger_channels.

Read paths join crm.v_blogger_totals for aggregate counts.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.blogger import (
    BloggerChannelOut,
    BloggerDetailOut,
    BloggerOut,
)


_LIST_SQL = """
SELECT b.id, b.display_handle, b.real_name, b.status,
       b.default_marketer_id,
       b.price_story_default, b.price_reels_default,
       b.created_at, b.updated_at
FROM crm.bloggers b
WHERE b.archived_at IS NULL
  {status_filter}
  {marketer_filter}
  {cursor_filter}
ORDER BY b.updated_at DESC, b.id DESC
LIMIT :limit
"""


def list_bloggers(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    marketer_id: int | None = None,
    q: str | None = None,
) -> tuple[list[BloggerOut], str | None]:
    """Return (rows, next_cursor). Rows length ≤ limit.

    Note: combining ``q`` with ``cursor`` has undefined pagination behavior
    because ``q`` filters post-fetch (after has_more is computed). Use the
    dedicated full-text search endpoint (T18) for query-driven listings;
    ``q`` here is convenience-only for the unfiltered first page.
    """
    params: dict[str, Any] = {"limit": limit + 1}  # one extra to detect "more"

    status_filter = ""
    if status:
        status_filter = "AND b.status = :status"
        params["status"] = status

    marketer_filter = ""
    if marketer_id is not None:
        marketer_filter = "AND b.default_marketer_id = :marketer_id"
        params["marketer_id"] = marketer_id

    cursor_filter = ""
    decoded = decode_cursor(cursor)
    if decoded is not None:
        cursor_ts, cursor_id = decoded
        cursor_filter = (
            "AND (b.updated_at, b.id) < (:cursor_ts, :cursor_id)"
        )
        params["cursor_ts"] = cursor_ts
        params["cursor_id"] = cursor_id

    sql = _LIST_SQL.format(
        status_filter=status_filter,
        marketer_filter=marketer_filter,
        cursor_filter=cursor_filter,
    )

    rows = session.execute(text(sql), params).mappings().all()

    if q:
        # Full-text via GIN handled by `search_bloggers` — this filter is
        # exact-prefix only for now; UI uses the dedicated /search endpoint.
        rows = [r for r in rows if q.lower() in (r["display_handle"] or "").lower()]

    has_more = len(rows) > limit
    rows = rows[:limit]

    out = [BloggerOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["updated_at"], rows[-1]["id"])
        if has_more and rows
        else None
    )
    return out, next_cursor


_DETAIL_SQL = """
SELECT b.*,
       COALESCE(t.integrations_count, 0)  AS integrations_count,
       COALESCE(t.integrations_done, 0)   AS integrations_done,
       t.last_integration_at,
       COALESCE(t.total_spent, 0)         AS total_spent,
       t.avg_cpm_fact
FROM crm.bloggers b
LEFT JOIN crm.v_blogger_totals t ON t.blogger_id = b.id
WHERE b.id = :id AND b.archived_at IS NULL
"""

_CHANNELS_SQL = """
SELECT id, channel, handle, url
FROM crm.blogger_channels
WHERE blogger_id = :blogger_id
ORDER BY channel, id
"""


def get_blogger(session: Session, blogger_id: int) -> BloggerDetailOut | None:
    row = session.execute(text(_DETAIL_SQL), {"id": blogger_id}).mappings().first()
    if row is None:
        return None

    channels = session.execute(
        text(_CHANNELS_SQL), {"blogger_id": blogger_id}
    ).mappings().all()

    payload: dict[str, Any] = dict(row)
    payload["channels"] = [BloggerChannelOut(**dict(c)) for c in channels]
    return BloggerDetailOut(**payload)


_INSERT_SQL = """
INSERT INTO crm.bloggers (
    display_handle, real_name, status, default_marketer_id,
    price_story_default, price_reels_default,
    contact_tg, contact_email, contact_phone, notes
) VALUES (
    :display_handle, :real_name, :status, :default_marketer_id,
    :price_story_default, :price_reels_default,
    :contact_tg, :contact_email, :contact_phone, :notes
)
RETURNING id
"""


def create_blogger(
    session: Session,
    **fields: Any,
) -> int:
    payload = {
        "display_handle": fields.get("display_handle"),
        "real_name": fields.get("real_name"),
        "status": fields.get("status", "new"),
        "default_marketer_id": fields.get("default_marketer_id"),
        "price_story_default": fields.get("price_story_default"),
        "price_reels_default": fields.get("price_reels_default"),
        "contact_tg": fields.get("contact_tg"),
        "contact_email": fields.get("contact_email"),
        "contact_phone": fields.get("contact_phone"),
        "notes": fields.get("notes"),
    }
    new_id = session.execute(text(_INSERT_SQL), payload).scalar_one()
    return int(new_id)


def update_blogger(
    session: Session,
    blogger_id: int,
    fields: dict[str, Any],
) -> None:
    if not fields:
        return
    allowed = {
        "display_handle", "real_name", "status", "default_marketer_id",
        "price_story_default", "price_reels_default",
        "contact_tg", "contact_email", "contact_phone", "notes",
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    # k comes from the `allowed` whitelist above — not user-controlled.
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = (
        f"UPDATE crm.bloggers SET {set_clause}, updated_at = now() "
        f"WHERE id = :id AND archived_at IS NULL"
    )
    session.execute(text(sql), {**fields, "id": blogger_id})
