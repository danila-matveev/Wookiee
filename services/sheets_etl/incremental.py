"""Incremental ETL helpers — filter transformed rows to only those needing upsert.

The full ETL (`run.py` without flags) processes all sheet rows every time.
For 6h-cadence cron we want to skip rows already present and unchanged.
We compare `sheet_row_id` (MD5 of source content) — same id = same content.
"""
from __future__ import annotations

from typing import Iterable


def existing_sheet_row_ids(conn, table: str) -> set[str]:
    """Return the set of sheet_row_id values currently in `table`.

    Caller passes a fully-qualified table name like 'crm.bloggers'.
    Returns empty set if table missing or empty.
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT sheet_row_id FROM {table} WHERE sheet_row_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def filter_new_rows(rows: Iterable[dict], existing: set[str]) -> list[dict]:
    """Return only rows whose `sheet_row_id` is NOT in `existing`.

    Rows without `sheet_row_id` (e.g., synthesized link rows) pass through
    unchanged — let the upsert dedup them on the natural conflict target.
    """
    return [r for r in rows if r.get("sheet_row_id") not in existing or "sheet_row_id" not in r]
