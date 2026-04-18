"""Logistics data layer — Supabase writes for WB tariffs and related ETL."""
from __future__ import annotations

import logging

from shared.data_layer._connection import _get_supabase_connection

logger = logging.getLogger(__name__)

__all__ = ["upsert_wb_tariffs"]


_UPSERT_WB_TARIFFS_SQL = """
INSERT INTO wb_tariffs (dt, warehouse_name, delivery_coef, logistics_1l,
                        logistics_extra_l, storage_1l_day, acceptance, storage_coef, geo_name)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (dt, warehouse_name) DO UPDATE SET
    delivery_coef     = EXCLUDED.delivery_coef,
    logistics_1l      = EXCLUDED.logistics_1l,
    logistics_extra_l = EXCLUDED.logistics_extra_l,
    storage_1l_day    = EXCLUDED.storage_1l_day,
    acceptance        = EXCLUDED.acceptance,
    storage_coef      = EXCLUDED.storage_coef,
    geo_name          = EXCLUDED.geo_name
"""


def upsert_wb_tariffs(rows: list[tuple]) -> int:
    """UPSERT строк `wb_tariffs` в Supabase.

    rows: последовательность кортежей в порядке колонок UPSERT-SQL выше.
    Возвращает количество переданных строк (executemany не отдаёт rowcount
    для всех драйверов, поэтому возвращаем len(rows)).
    """
    if not rows:
        return 0
    conn = _get_supabase_connection()
    try:
        cur = conn.cursor()
        cur.executemany(_UPSERT_WB_TARIFFS_SQL, rows)
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return len(rows)
