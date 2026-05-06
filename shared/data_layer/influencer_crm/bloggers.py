"""Read+write queries for crm.bloggers + crm.blogger_channels.

Read paths join crm.v_blogger_totals for aggregate counts.
"""
from __future__ import annotations

from typing import Any, Optional

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
  {channel_filter}
  {cursor_filter}
ORDER BY b.updated_at DESC, b.id DESC
LIMIT :limit
"""


def list_bloggers(
    session: Session,
    *,
    limit: int = 50,
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    marketer_id: Optional[int] = None,
    q: Optional[str] = None,
    channel: Optional[str] = None,
) -> tuple[list[BloggerOut], Optional[str]]:
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

    channel_filter = ""
    if channel:
        channel_filter = (
            "AND b.id IN ("
            "  SELECT blogger_id FROM crm.blogger_channels WHERE channel = :channel"
            ")"
        )
        params["channel"] = channel

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
        channel_filter=channel_filter,
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


def search_bloggers(session: Session, q: str, limit: int = 10) -> list[BloggerOut]:
    """Trigram search on display_handle + real_name + notes via idx_bloggers_search."""
    rows = session.execute(
        text(
            "SELECT id, display_handle, real_name, status, default_marketer_id, "
            "       price_story_default, price_reels_default, created_at, updated_at "
            "FROM crm.bloggers "
            "WHERE archived_at IS NULL AND ("
            "    display_handle ILIKE '%' || :q || '%' "
            " OR COALESCE(real_name, '') ILIKE '%' || :q || '%' "
            " OR COALESCE(notes, '') ILIKE '%' || :q || '%'"
            ") ORDER BY updated_at DESC LIMIT :limit"
        ),
        {"q": q, "limit": limit},
    ).mappings().all()
    return [BloggerOut(**dict(r)) for r in rows]


_SUMMARY_SQL = """
SELECT
    b.id, b.display_handle, b.real_name, b.status,
    b.default_marketer_id, b.price_story_default::text, b.price_reels_default::text,
    b.created_at::text, b.updated_at::text,
    COALESCE(
        json_agg(
            DISTINCT jsonb_build_object(
                'id',      bc.id,
                'channel', bc.channel,
                'handle',  bc.handle,
                'url',     bc.url
            )
        ) FILTER (WHERE bc.id IS NOT NULL),
        '[]'::json
    ) AS channels,
    COALESCE(t.integrations_count, 0)  AS integrations_count,
    COALESCE(t.integrations_done, 0)   AS integrations_done,
    t.last_integration_at::text        AS last_integration_at,
    COALESCE(t.total_spent::text, '0') AS total_spent,
    CASE
        WHEN SUM(i.fact_views) > 0
        THEN ROUND(
            SUM(i.total_cost::numeric) / NULLIF(SUM(i.fact_views), 0) * 1000,
            2
        )::text
        ELSE NULL
    END AS avg_cpm_fact
FROM crm.bloggers b
LEFT JOIN crm.blogger_channels bc      ON bc.blogger_id = b.id
LEFT JOIN crm.v_blogger_totals t       ON t.blogger_id  = b.id
LEFT JOIN crm.integrations i           ON i.blogger_id  = b.id
                                       AND i.archived_at IS NULL
WHERE b.archived_at IS NULL
  {status_filter}
  {q_filter}
  {channel_filter}
GROUP BY b.id, b.display_handle, b.real_name, b.status,
         b.default_marketer_id, b.price_story_default, b.price_reels_default,
         b.created_at, b.updated_at,
         t.integrations_count, t.integrations_done,
         t.last_integration_at, t.total_spent
ORDER BY b.updated_at DESC NULLS LAST, b.id DESC
LIMIT :limit OFFSET :offset
"""

_SUMMARY_COUNT_SQL = """
SELECT COUNT(DISTINCT b.id)
FROM crm.bloggers b
LEFT JOIN crm.blogger_channels bc ON bc.blogger_id = b.id
WHERE b.archived_at IS NULL
  {status_filter}
  {q_filter}
  {channel_filter}
"""


def list_bloggers_summary(
    session: Session,
    *,
    limit: int = 200,
    offset: int = 0,
    status: Optional[str] = None,
    q: Optional[str] = None,
    channel: Optional[str] = None,
) -> tuple[list, int]:
    """Return (rows, total_count) for table view.

    Uses offset pagination (not cursor) because table supports sorting/jumping.
    Limit capped at 500.
    """
    import json as _json

    from services.influencer_crm.schemas.blogger import BloggerSummaryOut, ChannelBrief

    limit = min(limit, 500)
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    status_filter = ""
    if status:
        status_filter = "AND b.status = :status"
        params["status"] = status

    q_filter = ""
    if q:
        q_filter = "AND LOWER(b.display_handle) LIKE LOWER(:q_pattern)"
        params["q_pattern"] = f"%{q}%"

    channel_filter = ""
    if channel:
        channel_filter = (
            "AND b.id IN ("
            "  SELECT blogger_id FROM crm.blogger_channels WHERE channel = :channel"
            ")"
        )
        params["channel"] = channel

    fmt = dict(
        status_filter=status_filter,
        q_filter=q_filter,
        channel_filter=channel_filter,
    )

    rows = session.execute(
        text(_SUMMARY_SQL.format(**fmt)), params
    ).mappings().all()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = session.execute(
        text(_SUMMARY_COUNT_SQL.format(**fmt)), count_params
    ).scalar() or 0

    items = []
    for r in rows:
        channels_raw = r["channels"]
        if isinstance(channels_raw, str):
            channels_raw = _json.loads(channels_raw)
        channels = [ChannelBrief(**c) for c in (channels_raw or [])]
        row_dict = dict(r)
        row_dict.pop("channels", None)
        items.append(BloggerSummaryOut(**row_dict, channels=channels))
    return items, total
