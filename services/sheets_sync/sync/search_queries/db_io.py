"""Persist WB search-query analytics to Supabase.

Two tables:
- marketing.search_queries_weekly         — per (week, word) aggregate
- marketing.search_query_product_breakdown — per (week, word, nm_id) detail
"""
from __future__ import annotations

import logging
from datetime import date

import psycopg2.extras

from services.sheets_etl.loader import get_conn

logger = logging.getLogger(__name__)


_SQW_COLS = ("week_start", "search_word", "frequency", "open_card", "add_to_cart", "orders")
_SQW_UPSERT_SQL = f"""
INSERT INTO marketing.search_queries_weekly ({", ".join(_SQW_COLS)})
VALUES %s
ON CONFLICT (week_start, search_word) DO UPDATE SET
    frequency   = EXCLUDED.frequency,
    open_card   = EXCLUDED.open_card,
    add_to_cart = EXCLUDED.add_to_cart,
    orders      = EXCLUDED.orders,
    captured_at = now()
"""


_SQPB_COLS = (
    "week_start", "search_word", "nm_id", "artikul_id",
    "sku_label", "model_code", "open_card", "add_to_cart", "orders",
)
_SQPB_UPSERT_SQL = f"""
INSERT INTO marketing.search_query_product_breakdown ({", ".join(_SQPB_COLS)})
VALUES %s
ON CONFLICT (week_start, search_word, nm_id) DO UPDATE SET
    artikul_id  = EXCLUDED.artikul_id,
    sku_label   = EXCLUDED.sku_label,
    model_code  = EXCLUDED.model_code,
    open_card   = EXCLUDED.open_card,
    add_to_cart = EXCLUDED.add_to_cart,
    orders      = EXCLUDED.orders,
    captured_at = now()
"""


def write_weekly(week_start: date, words: dict[str, dict]) -> int:
    """Upsert per-word aggregate for one week.

    words: {search_word: {frequency, openCard, addToCart, orders}}
    """
    if not words:
        return 0
    rows = [
        (
            week_start, word,
            int(m.get("frequency") or 0),
            int(m.get("openCard") or 0),
            int(m.get("addToCart") or 0),
            int(m.get("orders") or 0),
        )
        for word, m in words.items()
    ]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _SQW_UPSERT_SQL, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def write_product_breakdown(week_start: date, items: list[dict]) -> int:
    """Upsert per (week × word × nm_id) detail for one week.

    items: list of {search_word, nm_id, openCard, addToCart, orders}
           (already filtered to tracked words; cabinet/dedup handled upstream).

    Resolves nm_id → public.artikuly.id via JOIN with public.modeli to cache
    sku_label and model_code (denormalized for fast UI reads).
    """
    if not items:
        return 0

    # Aggregate by (word, nm_id): same nmId may appear from ИП and ООО cabinets
    # for the same search word — we want one row per (word, nm_id) per week.
    from collections import defaultdict
    agg: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"open_card": 0, "add_to_cart": 0, "orders": 0}
    )
    for it in items:
        word = (it.get("search_word") or "").strip()
        if not word:
            continue
        try:
            nm_id = int(it.get("nm_id") or 0)
        except (TypeError, ValueError):
            nm_id = 0
        if nm_id == 0:
            continue
        bucket = agg[(word, nm_id)]
        bucket["open_card"]   += int(it.get("openCard") or 0)
        bucket["add_to_cart"] += int(it.get("addToCart") or 0)
        bucket["orders"]      += int(it.get("orders") or 0)

    if not agg:
        return 0

    nm_ids = sorted({nm for _, nm in agg.keys()})

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.nomenklatura_wb, a.id, a.artikul, m.kod
                FROM public.artikuly a
                LEFT JOIN public.modeli m ON m.id = a.model_id
                WHERE a.nomenklatura_wb = ANY(%s)
                """,
                (nm_ids,),
            )
            nm_map: dict[int, tuple[int, str | None, str | None]] = {
                row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()
            }

        unresolved: set[int] = set()
        rows: list[tuple] = []
        for (word, nm_id), b in agg.items():
            info = nm_map.get(nm_id)
            if info:
                artikul_id, artikul_str, m_kod = info
                sku_label = artikul_str or f"nm_id:{nm_id}"
                # Project convention: model_key = LOWER(SPLIT_PART(article, '/', 1))
                model_code = (sku_label.split("/")[0] or m_kod or "").strip().lower() or None
            else:
                unresolved.add(nm_id)
                artikul_id = None
                sku_label = None
                model_code = None
            rows.append((
                week_start, word, nm_id, artikul_id,
                sku_label, model_code,
                b["open_card"], b["add_to_cart"], b["orders"],
            ))

        if unresolved:
            logger.info(
                "search_query_product_breakdown: %d nm_id without artikuly row (kept with NULL artikul_id)",
                len(unresolved),
            )

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _SQPB_UPSERT_SQL, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()
