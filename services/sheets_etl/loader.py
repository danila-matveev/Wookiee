"""DB writers: UPSERT by sheet_row_id + simple FK lookups."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "sku_database" / ".env")

# Supabase sets statement_timeout=30s for all connections by default.
# ETL bulk-loads can exceed this on large sheets (substitute_article_metrics_weekly
# had 4/5 failures). We disable the timeout at the session level so the full
# batch can complete. The timeout is scoped to this connection only.
PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST") or os.getenv("SUPABASE_HOST"),
    "port": int(os.getenv("POSTGRES_PORT") or os.getenv("SUPABASE_PORT") or "5432"),
    "database": os.getenv("POSTGRES_DB") or os.getenv("SUPABASE_DB") or "postgres",
    "user": os.getenv("POSTGRES_USER") or os.getenv("SUPABASE_USER"),
    "password": os.getenv("POSTGRES_PASSWORD") or os.getenv("SUPABASE_PASSWORD"),
    "sslmode": "require",
    "options": "-csearch_path=crm,public -cstatement_timeout=0",
}

# Batch size for execute_values: number of rows per multi-row INSERT.
# 500 rows/batch keeps individual statements well under any advisory timeout
# while avoiding excessive round-trips.
_BATCH_SIZE = 500


def get_conn():
    return psycopg2.connect(**PG_CONFIG)


def upsert(conn, table: str, rows: list[dict[str, Any]],
           conflict_col: str = "sheet_row_id",
           no_update_cols: list[str] | None = None) -> int:
    """INSERT … ON CONFLICT (conflict_col) DO UPDATE for every column except conflict_col.

    Uses execute_values for multi-row batching instead of row-by-row execute,
    which avoids statement_timeout on large sheets.

    Args:
        no_update_cols: Optional list of column names to exclude from the
            DO UPDATE SET clause. Use this to preserve values set manually
            in the DB (e.g. stage on kanban cards) that should not be
            overwritten by the ETL run.
    """
    if not rows:
        return 0
    cols = list(rows[0].keys())
    _skip = {conflict_col, *(no_update_cols or [])}
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in _skip)

    if not update_set:
        sql = f'INSERT INTO {table} ({", ".join(cols)}) VALUES %s ON CONFLICT ({conflict_col}) DO NOTHING'
    else:
        sql = (
            f'INSERT INTO {table} ({", ".join(cols)}) VALUES %s '
            f'ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}'
        )
    values = [[r[c] for c in cols] for r in rows]
    with conn.cursor() as cur:
        for i in range(0, len(values), _BATCH_SIZE):
            psycopg2.extras.execute_values(cur, sql, values[i:i + _BATCH_SIZE])
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
    Uses execute_values for multi-row batching to avoid statement_timeout.
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
    update_cols = [c for c in cols if c not in non_update]
    if update_cols:
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = (
            f'INSERT INTO {table} ({", ".join(cols)}) VALUES %s '
            f'ON CONFLICT {conflict_target_sql} DO UPDATE SET {update_set}'
        )
    else:
        sql = (
            f'INSERT INTO {table} ({", ".join(cols)}) VALUES %s '
            f'ON CONFLICT {conflict_target_sql} DO NOTHING'
        )
    values = [[r[c] for c in cols] for r in rows]
    with conn.cursor() as cur:
        for i in range(0, len(values), _BATCH_SIZE):
            psycopg2.extras.execute_values(cur, sql, values[i:i + _BATCH_SIZE])
    conn.commit()
    return len(rows)
