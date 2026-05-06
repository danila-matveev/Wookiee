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
