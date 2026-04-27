#!/usr/bin/env python3
"""
Migration 008: Influencer CRM (schema v4.1).

Creates 22 tables for blogger relationship management on top of sku_database.
Source DDL: sku_database/database/migrations/008_influencer_crm.sql.

Tables: marketers, tags, bloggers, blogger_channels, blogger_tags,
content_brief_templates, briefs, brief_versions, substitute_articles,
substitute_article_metrics_weekly, promo_codes, integrations,
integration_substitute_articles, integration_promo_codes,
integration_posts, integration_metrics_snapshots, integration_stage_history,
integration_tags, blogger_candidates, branded_queries, audit_log,
sheets_sync_state.

Idempotent only via DROP-and-recreate (use --force). Default behaviour:
fail if any CRM table already exists, to prevent accidental overwrite.

Usage:
    python scripts/migrations/008_create_influencer_crm.py [--dry-run] [--force]

Connects via service_role (postgres user) — RLS does not apply.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require",
}

SQL_FILE = Path(__file__).resolve().parents[2] / "database" / "migrations" / "008_influencer_crm.sql"

CRM_TABLES = [
    "marketers", "tags", "bloggers", "blogger_channels", "blogger_tags",
    "content_brief_templates", "briefs", "brief_versions",
    "substitute_articles", "substitute_article_metrics_weekly",
    "promo_codes", "integrations",
    "integration_substitute_articles", "integration_promo_codes",
    "integration_posts", "integration_metrics_snapshots", "integration_stage_history",
    "integration_tags", "blogger_candidates", "branded_queries",
    "audit_log", "sheets_sync_state",
]


def existing_crm_tables(cur) -> list[str]:
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='crm' AND table_name = ANY(%s)",
        (CRM_TABLES,),
    )
    return [row[0] for row in cur.fetchall()]


def drop_crm_objects(cur) -> None:
    """Drop the entire crm schema; CASCADE handles all FK/trigger/view chains."""
    cur.execute("DROP SCHEMA IF EXISTS crm CASCADE")


def apply_migration(dry_run: bool, force: bool) -> int:
    if not SQL_FILE.exists():
        print(f"ERROR: SQL file not found: {SQL_FILE}", file=sys.stderr)
        return 2

    sql = SQL_FILE.read_text(encoding="utf-8")
    print("=" * 60)
    print("Migration 008: Influencer CRM (schema v4.1)")
    print("=" * 60)
    print(f"SQL file:    {SQL_FILE}")
    print(f"Bytes:       {len(sql)}")
    print(f"CREATE TABLE statements: {sql.count('CREATE TABLE')}")
    print(f"Dry-run:     {dry_run}")
    print(f"Force:       {force}")

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            existing = existing_crm_tables(cur)
            if existing:
                if not force:
                    print(
                        f"\nERROR: existing CRM tables detected ({len(existing)}): {existing}",
                        file=sys.stderr,
                    )
                    print("Re-run with --force to drop and recreate.", file=sys.stderr)
                    return 2
                print(f"\n--force: dropping {len(existing)} existing CRM tables...")
                drop_crm_objects(cur)
                conn.commit()
                print("Existing CRM objects dropped.")

            if dry_run:
                print(f"\nDRY RUN: would apply {len(sql)} bytes of SQL "
                      f"({sql.count('CREATE TABLE')} tables).")
                return 0

            print(f"\nApplying migration 008 ({len(sql)} bytes)...")
            with conn.cursor() as cur2:
                cur2.execute(sql)
            conn.commit()

            with conn.cursor() as cur3:
                applied = existing_crm_tables(cur3)
            if len(applied) != 22:
                missing = set(CRM_TABLES) - set(applied)
                print(
                    f"FAIL: expected 22 tables, got {len(applied)}. "
                    f"Missing: {missing}",
                    file=sys.stderr,
                )
                return 1
            print(f"OK: 22 CRM tables created.")
            return 0
    except Exception as e:
        conn.rollback()
        print(f"FAILED (rolled back): {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Apply migration 008 (Influencer CRM v4.1)")
    p.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    p.add_argument("--force", action="store_true",
                   help="Drop existing CRM tables before re-applying")
    args = p.parse_args()
    return apply_migration(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
