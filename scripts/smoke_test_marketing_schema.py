#!/usr/bin/env python3
"""Smoke test: verify marketing schema Phase 1 migration.

Run BEFORE migration → expect failures (schema doesn't exist).
Run AFTER migration  → expect all checks pass.

Usage:
    python scripts/smoke_test_marketing_schema.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_PG = {
    "host":     os.getenv("POSTGRES_HOST") or os.getenv("SUPABASE_HOST"),
    "port":     int(os.getenv("POSTGRES_PORT") or os.getenv("SUPABASE_PORT") or "5432"),
    "database": os.getenv("POSTGRES_DB") or os.getenv("SUPABASE_DB") or "postgres",
    "user":     os.getenv("POSTGRES_USER") or os.getenv("SUPABASE_USER"),
    "password": os.getenv("POSTGRES_PASSWORD") or os.getenv("SUPABASE_PASSWORD"),
    "sslmode":  "require",
    "options":  "-csearch_path=marketing,crm,public -cstatement_timeout=10000",
}

# (label, sql, expected_value)
CHECKS: list[tuple[str, str, object]] = [
    (
        "marketing schema exists",
        "SELECT count(*)::int FROM information_schema.schemata WHERE schema_name = 'marketing'",
        1,
    ),
    (
        "promo_stats_weekly table exists",
        "SELECT count(*)::int FROM information_schema.tables "
        "WHERE table_schema='marketing' AND table_name='promo_stats_weekly'",
        1,
    ),
    (
        "promo_stats_weekly RLS enabled",
        "SELECT relrowsecurity FROM pg_class "
        "WHERE relname='promo_stats_weekly' "
        "AND relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='marketing')",
        True,
    ),
    (
        "crm.promo_codes.name column exists",
        "SELECT count(*)::int FROM information_schema.columns "
        "WHERE table_schema='crm' AND table_name='promo_codes' AND column_name='name'",
        1,
    ),
    (
        "marketing.promo_codes view exists",
        "SELECT count(*)::int FROM information_schema.views "
        "WHERE table_schema='marketing' AND table_name='promo_codes'",
        1,
    ),
    (
        "marketing.search_queries view exists",
        "SELECT count(*)::int FROM information_schema.views "
        "WHERE table_schema='marketing' AND table_name='search_queries'",
        1,
    ),
    (
        "marketing.search_query_stats_weekly view exists",
        "SELECT count(*)::int FROM information_schema.views "
        "WHERE table_schema='marketing' AND table_name='search_query_stats_weekly'",
        1,
    ),
    (
        "marketing.promo_codes row count = 3",
        "SELECT count(*)::int FROM marketing.promo_codes",
        3,
    ),
    (
        "marketing.search_queries row count = 85",
        "SELECT count(*)::int FROM marketing.search_queries",
        85,
    ),
    (
        "marketing.search_query_stats_weekly row count = 2565",
        "SELECT count(*)::int FROM marketing.search_query_stats_weekly",
        2565,
    ),
    (
        "search_query_stats_weekly exposes search_query_id (not substitute_article_id)",
        "SELECT count(*)::int FROM information_schema.columns "
        "WHERE table_schema='marketing' AND table_name='search_query_stats_weekly' "
        "AND column_name='search_query_id'",
        1,
    ),
    (
        "search_queries exposes channel (not purpose)",
        "SELECT count(*)::int FROM information_schema.columns "
        "WHERE table_schema='marketing' AND table_name='search_queries' "
        "AND column_name='channel'",
        1,
    ),
]


def run_check(conn, label: str, sql: str, expected: object) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            result = row[0] if row is not None else None
    except Exception as exc:
        conn.rollback()
        print(f"  ✗ {label}: ERROR — {exc}")
        return False
    ok = result == expected
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}: got {result!r}" + (f" (expected {expected!r})" if not ok else ""))
    return ok


def main() -> int:
    try:
        conn = psycopg2.connect(**_PG)
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return 1

    failures = 0
    print("Marketing schema smoke test\n" + "=" * 40)
    for label, sql, expected in CHECKS:
        if not run_check(conn, label, sql, expected):
            failures += 1
    conn.close()

    print("\n" + ("All checks passed ✓" if failures == 0 else f"{failures} check(s) FAILED ✗"))
    return failures


if __name__ == "__main__":
    sys.exit(main())
