"""DB writers: UPSERT by sheet_row_id + simple FK lookups."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "sku_database" / ".env")

PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST") or os.getenv("SUPABASE_HOST"),
    "port": int(os.getenv("POSTGRES_PORT") or os.getenv("SUPABASE_PORT") or "5432"),
    "database": os.getenv("POSTGRES_DB") or os.getenv("SUPABASE_DB") or "postgres",
    "user": os.getenv("POSTGRES_USER") or os.getenv("SUPABASE_USER"),
    "password": os.getenv("POSTGRES_PASSWORD") or os.getenv("SUPABASE_PASSWORD"),
    "sslmode": "require",
    "options": "-csearch_path=crm,public",
}


def get_conn():
    return psycopg2.connect(**PG_CONFIG)


def upsert(conn, table: str, rows: list[dict[str, Any]],
           conflict_col: str = "sheet_row_id") -> int:
    """INSERT … ON CONFLICT (conflict_col) DO UPDATE for every column except conflict_col."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != conflict_col)

    sql = (
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}'
    )
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, [r[c] for c in cols])
    conn.commit()
    return len(rows)


def lookup_id(conn, table: str, where: dict[str, Any]) -> int | None:
    keys = list(where.keys())
    sql = (
        f'SELECT id FROM {table} WHERE '
        + " AND ".join(f"{k} = %s" for k in keys)
        + " LIMIT 1"
    )
    with conn.cursor() as cur:
        cur.execute(sql, [where[k] for k in keys])
        row = cur.fetchone()
    return row[0] if row else None


def insert_junction(conn, table: str, rows: list[dict[str, Any]],
                    conflict_cols: tuple[str, ...] | None = None,
                    conflict_target_sql: str | None = None) -> int:
    """Junction tables (no sheet_row_id) — UPSERT by composite key.

    Either pass conflict_cols (simple column list) or conflict_target_sql
    (full expression like '(channel, LOWER(handle))' for expression indexes).
    """
    if not rows:
        return 0
    if conflict_target_sql is None:
        if not conflict_cols:
            raise ValueError("Need conflict_cols or conflict_target_sql")
        conflict_target_sql = "(" + ", ".join(conflict_cols) + ")"
        non_update = set(conflict_cols)
    else:
        non_update = set()

    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    update_cols = [c for c in cols if c not in non_update]
    if update_cols:
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = (
            f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
            f'ON CONFLICT {conflict_target_sql} DO UPDATE SET {update_set}'
        )
    else:
        sql = (
            f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
            f'ON CONFLICT {conflict_target_sql} DO NOTHING'
        )
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, [r[c] for c in cols])
    conn.commit()
    return len(rows)
