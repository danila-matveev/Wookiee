"""Write aggregated promo metrics to marketing.promo_stats_weekly."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import psycopg2.extras

from services.sheets_etl.loader import get_conn

logger = logging.getLogger(__name__)

_COLS = [
    "promo_code_id", "week_start", "sales_rub", "payout_rub",
    "orders_count", "returns_count", "avg_discount_pct", "avg_check",
]
_UPDATE_SET = ", ".join(
    f"{c} = EXCLUDED.{c}" for c in _COLS if c not in ("promo_code_id", "week_start")
)
_UPSERT_SQL = (
    f'INSERT INTO marketing.promo_stats_weekly ({", ".join(_COLS)}) VALUES %s '
    f'ON CONFLICT (promo_code_id, week_start) DO UPDATE SET {_UPDATE_SET}'
)


def _d2(val: float | None) -> Decimal | None:
    if val is None:
        return None
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def write_weekly_metrics(week_start: date, metrics_by_uuid: dict[str, dict]) -> int:
    """Upsert aggregated promo metrics for one week into marketing.promo_stats_weekly.

    metrics_by_uuid: {uuid_str: {sales_rub, ppvz_rub, orders_count, returns_count, avg_discount_pct}}
    Returns number of rows written.
    """
    if not metrics_by_uuid:
        return 0

    conn = get_conn()
    try:
        rows = _resolve_rows(conn, week_start, metrics_by_uuid)
        if not rows:
            return 0
        return _upsert(conn, rows)
    finally:
        conn.close()


def _auto_insert_promo(conn, uuid: str) -> int | None:
    """Insert placeholder promo code for unknown WB UUID. name=NULL for manual fill-in."""
    placeholder_code = f"WB:{uuid.upper()}"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO crm.promo_codes (code, external_uuid, status) "
            "VALUES (%s, %s::uuid, 'active') "
            "ON CONFLICT (external_uuid) DO NOTHING RETURNING id",
            (placeholder_code, uuid),
        )
        rec = cur.fetchone()
        if rec is None:
            cur.execute(
                "SELECT id FROM crm.promo_codes WHERE external_uuid = %s::uuid LIMIT 1",
                (uuid,),
            )
            rec = cur.fetchone()
    conn.commit()
    if rec:
        logger.info("Auto-inserted placeholder promo_code: code=%s uuid=%s id=%d",
                    placeholder_code, uuid, rec[0])
        return rec[0]
    return None


def _resolve_rows(conn, week_start: date, metrics_by_uuid: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    with conn.cursor() as cur:
        for uuid, m in metrics_by_uuid.items():
            cur.execute(
                "SELECT id FROM crm.promo_codes WHERE external_uuid = %s::uuid LIMIT 1",
                (uuid,),
            )
            rec = cur.fetchone()
            if rec is None:
                promo_code_id = _auto_insert_promo(conn, uuid)
                if promo_code_id is None:
                    logger.warning("Could not auto-insert uuid %s — skipped", uuid)
                    continue
            else:
                promo_code_id = rec[0]

            sales = m.get("sales_rub") or 0.0
            orders = m.get("orders_count") or 0
            avg_check = (sales / orders) if orders > 0 else None

            rows.append({
                "promo_code_id": promo_code_id,
                "week_start": week_start,
                "sales_rub": _d2(sales),
                "payout_rub": _d2(m.get("ppvz_rub")),
                "orders_count": orders,
                "returns_count": m.get("returns_count") or 0,
                "avg_discount_pct": _d2(m.get("avg_discount_pct")),
                "avg_check": _d2(avg_check),
            })
    return rows


def _upsert(conn, rows: list[dict]) -> int:
    values = [[r[c] for c in _COLS] for r in rows]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, _UPSERT_SQL, values)
    conn.commit()
    return len(rows)


_PB_UPSERT_SQL = """
INSERT INTO marketing.promo_product_breakdown
    (promo_code_id, week_start, artikul_id, sku_label, model_code, qty, amount_rub)
VALUES %s
ON CONFLICT (promo_code_id, week_start, artikul_id) DO UPDATE SET
    sku_label   = EXCLUDED.sku_label,
    model_code  = EXCLUDED.model_code,
    qty         = EXCLUDED.qty,
    amount_rub  = EXCLUDED.amount_rub,
    captured_at = now()
"""


def write_product_breakdown(
    week_start: date,
    rows_by_cabinet: dict[str, list[dict]],
) -> int:
    """Aggregate WB report rows by (promo UUID × nm_id) and upsert into
    marketing.promo_product_breakdown.

    rows_by_cabinet: {"ИП": [api_row, ...], "ООО": [api_row, ...]}

    Same WB sale appears in both cabinets' reports, so we dedup by srid
    (preferring ООО). Resolves nm_id → public.artikuly.id via JOIN; rows
    whose nm_id is missing from our catalog are skipped with a warning.
    Returns count of upserted rows.
    """
    from collections import defaultdict

    if not rows_by_cabinet:
        return 0

    seen_srid: set[str] = set()
    agg: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"qty": 0, "amount": 0.0, "sa_name": ""}
    )

    for cab in ("ООО", "ИП"):
        for row in rows_by_cabinet.get(cab, []):
            uuid = str(row.get("uuid_promocode") or "").strip().lower()
            if not uuid:
                continue
            # Dedup srid AFTER promo filter: a single srid can appear on both a
            # 'Продажа' row and a 'Логистика'/'Хранение' row; we only want to
            # dedup promo sales across cabinets.
            srid = str(row.get("srid") or "").strip()
            if srid:
                if srid in seen_srid:
                    continue
                seen_srid.add(srid)
            try:
                nm_id = int(row.get("nm_id") or 0)
            except (TypeError, ValueError):
                nm_id = 0
            if nm_id == 0:
                continue
            doc = (row.get("doc_type_name") or "").strip()
            qty = int(row.get("quantity") or 0) or 1
            try:
                retail = float(row.get("retail_amount") or 0.0)
            except (TypeError, ValueError):
                retail = 0.0

            bucket = agg[(uuid, nm_id)]
            if not bucket["sa_name"]:
                bucket["sa_name"] = (row.get("sa_name") or "").strip()
            if doc == "Продажа":
                bucket["qty"] += qty
                bucket["amount"] += retail
            elif doc in ("Возврат", "Корректный возврат"):
                bucket["qty"] -= qty
                bucket["amount"] -= retail

    if not agg:
        return 0

    nm_ids = sorted({nm for _, nm in agg.keys()})
    uuids = sorted({u for u, _ in agg.keys()})

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
            nm_map = {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}

            cur.execute(
                "SELECT external_uuid::text, id FROM crm.promo_codes "
                "WHERE external_uuid = ANY(%s::uuid[])",
                (uuids,),
            )
            uuid_to_id: dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

        rows_for_insert = []
        unresolved_nm: set[int] = set()
        unresolved_uuid: set[str] = set()

        for (uuid, nm_id), b in agg.items():
            promo_id = uuid_to_id.get(uuid)
            if not promo_id:
                unresolved_uuid.add(uuid)
                continue
            info = nm_map.get(nm_id)
            if not info:
                unresolved_nm.add(nm_id)
                continue
            artikul_id, artikul_str, m_kod = info
            sku_label = artikul_str or b["sa_name"] or f"nm_id:{nm_id}"
            # Project convention: model_key = LOWER(SPLIT_PART(article, '/', 1))
            model_code = (sku_label.split("/")[0] or m_kod or "").strip().lower() or None
            rows_for_insert.append((
                promo_id, week_start, artikul_id, sku_label,
                model_code, b["qty"], _d2(b["amount"]),
            ))

        if unresolved_nm:
            logger.info(
                "promo_product_breakdown: %d nm_id without artikuly row (skipped)",
                len(unresolved_nm),
            )
        if unresolved_uuid:
            logger.info(
                "promo_product_breakdown: %d uuids without crm.promo_codes row (skipped)",
                len(unresolved_uuid),
            )

        if not rows_for_insert:
            return 0

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _PB_UPSERT_SQL, rows_for_insert)
        conn.commit()
        return len(rows_for_insert)
    finally:
        conn.close()
