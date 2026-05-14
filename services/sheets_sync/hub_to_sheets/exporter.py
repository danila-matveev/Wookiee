"""Read export views from Supabase as (columns, rows) tuples."""
from __future__ import annotations

import logging
import os
from typing import Sequence

import psycopg2

logger = logging.getLogger(__name__)


def _connect():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        dbname=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )


def fetch_view(view_name: str) -> tuple[list[str], list[list[str]]]:
    """Fetch all rows from a Supabase view, returning (columns, rows).

    Values are normalised to strings (None → ""). Floats with trailing .0 are
    collapsed to integers so the sheet shows "26" rather than "26.0".
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"select * from {view_name}")
            columns = [d[0] for d in cur.description]
            raw_rows = cur.fetchall()
    finally:
        conn.close()

    rows: list[list[str]] = []
    for r in raw_rows:
        rows.append([_to_cell(v) for v in r])
    logger.debug("fetch_view %s → %d cols × %d rows", view_name, len(columns), len(rows))
    return columns, rows


def _to_cell(value: object) -> str:
    """Convert a DB value to its Sheets representation (string)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def fetch_views(view_names: Sequence[str]) -> dict[str, tuple[list[str], list[list[str]]]]:
    """Convenience: fetch many views via a single connection."""
    conn = _connect()
    out: dict[str, tuple[list[str], list[list[str]]]] = {}
    try:
        for view in view_names:
            with conn.cursor() as cur:
                cur.execute(f"select * from {view}")
                cols = [d[0] for d in cur.description]
                rows = [[_to_cell(v) for v in row] for row in cur.fetchall()]
                out[view] = (cols, rows)
    finally:
        conn.close()
    return out
