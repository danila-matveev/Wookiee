"""Slices: aggregate integrations per public.modeli_osnova.

A model_osnova rolls up multiple modeli (color variants). We map
substitute_articles → artikul_id → modeli.id → modeli_osnova.id.
"""
from __future__ import annotations
from typing import Optional

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.product import (
    ProductDetailIntegrationOut,
    ProductDetailOut,
    ProductSliceOut,
)


_AGG_CTE = """
WITH integration_models AS (
    SELECT DISTINCT i.id AS integration_id, mo.id AS model_osnova_id, mo.nazvanie_etiketka AS model_name,
           i.publish_date, i.total_cost, i.fact_revenue, i.stage, i.fact_views, i.fact_orders,
           b.display_handle AS blogger_handle
    FROM crm.integrations i
    JOIN crm.bloggers b ON b.id = i.blogger_id
    JOIN crm.integration_substitute_articles isa ON isa.integration_id = i.id
    JOIN crm.substitute_articles sa ON sa.id = isa.substitute_article_id
    JOIN public.artikuly a ON a.id = sa.artikul_id
    JOIN public.modeli m ON m.id = a.model_id
    JOIN public.modeli_osnova mo ON mo.id = m.model_osnova_id
    WHERE i.archived_at IS NULL
)
"""


def list_products(
    session: Session,
    *,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> tuple[list[ProductSliceOut], Optional[str]]:
    decoded = decode_cursor(cursor)
    having_clause = ""
    params: dict = {"limit": limit + 1}
    if decoded is not None:
        cursor_ts, cursor_id = decoded
        having_clause = (
            "HAVING (COALESCE(MAX(publish_date), '1900-01-01'::date), model_osnova_id) "
            "< (:cursor_ts::date, :cursor_id) "
        )
        params["cursor_ts"] = cursor_ts.date().isoformat()
        params["cursor_id"] = cursor_id

    sql = (
        _AGG_CTE
        + """
        SELECT model_osnova_id, MAX(model_name) AS model_name,
               COUNT(DISTINCT integration_id) AS integrations_count,
               COUNT(DISTINCT integration_id) FILTER (WHERE stage IN ('published','paid','done')) AS integrations_done,
               MAX(publish_date) AS last_publish_date,
               COALESCE(SUM(total_cost), 0) AS total_spent,
               COALESCE(SUM(fact_revenue), 0) AS total_revenue_fact
        FROM integration_models
        GROUP BY model_osnova_id
        """ + having_clause
        + " ORDER BY MAX(publish_date) DESC NULLS LAST, model_osnova_id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [ProductSliceOut(**dict(r)) for r in rows]

    next_cursor = None
    if has_more and rows and rows[-1]["last_publish_date"]:
        ts = datetime.combine(rows[-1]["last_publish_date"], datetime.min.time())
        next_cursor = encode_cursor(ts, rows[-1]["model_osnova_id"])
    return items, next_cursor


def get_product(session: Session, model_osnova_id: int) -> ProductDetailOut | None:
    sql = (
        _AGG_CTE
        + """
        SELECT model_osnova_id, MAX(model_name) AS model_name,
               COUNT(DISTINCT integration_id) AS integrations_count,
               COUNT(DISTINCT integration_id) FILTER (WHERE stage IN ('published','paid','done')) AS integrations_done,
               MAX(publish_date) AS last_publish_date,
               COALESCE(SUM(total_cost), 0) AS total_spent,
               COALESCE(SUM(fact_revenue), 0) AS total_revenue_fact
        FROM integration_models
        WHERE model_osnova_id = :model_osnova_id
        GROUP BY model_osnova_id
        """
    )
    head = session.execute(text(sql), {"model_osnova_id": model_osnova_id}).mappings().first()
    if head is None:
        return None

    sub_sql = (
        _AGG_CTE
        + """
        SELECT integration_id, blogger_handle, publish_date, stage, total_cost,
               fact_views, fact_orders, fact_revenue
        FROM integration_models
        WHERE model_osnova_id = :model_osnova_id
        ORDER BY publish_date DESC, integration_id DESC
        """
    )
    subs = session.execute(text(sub_sql), {"model_osnova_id": model_osnova_id}).mappings().all()

    payload = dict(head)
    payload["integrations"] = [ProductDetailIntegrationOut(**dict(s)) for s in subs]
    return ProductDetailOut(**payload)
