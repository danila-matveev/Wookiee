from __future__ import annotations
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.promo import PromoCodeOut, SubstituteArticleOut


def list_substitute_articles(
    session: Session, *, limit: int = 50, cursor: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[list[SubstituteArticleOut], Optional[str]]:
    params: dict = {"limit": limit + 1}
    where = []
    if status:
        where.append("AND status = :status")
        params["status"] = status
    decoded = decode_cursor(cursor)
    if decoded:
        ts, cid = decoded
        where.append("AND (created_at, id) < (:cts, :cid)")
        params["cts"] = ts
        params["cid"] = cid
    sql = (
        "SELECT id, code, artikul_id, purpose, status, created_at "
        "FROM crm.substitute_articles WHERE 1=1 "
        + " ".join(where)
        + " ORDER BY created_at DESC, id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [SubstituteArticleOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["created_at"], rows[-1]["id"])
        if has_more and rows and rows[-1]["created_at"]
        else None
    )
    return items, next_cursor


def list_promo_codes(
    session: Session, *, limit: int = 50, cursor: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[list[PromoCodeOut], Optional[str]]:
    params: dict = {"limit": limit + 1}
    where = []
    if status:
        where.append("AND status = :status")
        params["status"] = status
    decoded = decode_cursor(cursor)
    if decoded:
        ts, cid = decoded
        where.append("AND (valid_from, id) < (:cts, :cid)")
        params["cts"] = ts.date().isoformat()
        params["cid"] = cid
    sql = (
        "SELECT id, code, artikul_id, discount_pct AS discount_percent, status, "
        "       valid_from, valid_until "
        "FROM crm.promo_codes WHERE 1=1 "
        + " ".join(where)
        + " ORDER BY valid_from DESC NULLS LAST, id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [PromoCodeOut(**dict(r)) for r in rows]
    next_cursor = None
    if has_more and rows and rows[-1]["valid_from"]:
        from datetime import datetime
        ts = datetime.combine(rows[-1]["valid_from"], datetime.min.time())
        next_cursor = encode_cursor(ts, rows[-1]["id"])
    return items, next_cursor
