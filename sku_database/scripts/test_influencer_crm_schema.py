"""Smoke tests for Influencer CRM schema (migration 008).

Run AFTER migration is applied to verify the schema is healthy.
Connects via service_role pooler (same as application code and existing migrations).

All CRM objects live in the `crm` Postgres schema.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require",
    "options": "-csearch_path=crm,public",
}

INFLUENCER_CRM_TABLES = [
    "marketers", "tags", "bloggers", "blogger_channels", "blogger_tags",
    "content_brief_templates", "briefs", "brief_versions",
    "substitute_articles", "substitute_article_metrics_weekly",
    "promo_codes", "integrations",
    "integration_substitute_articles", "integration_promo_codes",
    "integration_posts", "integration_metrics_snapshots", "integration_stage_history",
    "integration_tags", "blogger_candidates", "branded_queries",
    "audit_log", "sheets_sync_state",
]


@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(**SUPABASE_CONFIG)
    try:
        yield c
    finally:
        c.close()


def test_22_tables_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'crm' AND table_name = ANY(%s)
            """,
            (INFLUENCER_CRM_TABLES,),
        )
        present = {row[0] for row in cur.fetchall()}
    missing = set(INFLUENCER_CRM_TABLES) - present
    assert not missing, f"Missing tables: {missing}"
    assert len(present) == 22, f"Expected 22, got {len(present)}"


EXPECTED_INDEXES = {
    "uq_blogger_channels_handle",
    "uq_integrations_erid",
    "idx_integrations_stage",
    "idx_isa_sub",
    "idx_isa_int",
    "uq_isa",
    "uq_ipc",
    "uq_v_blogger_totals",
    "idx_bq_trgm",
    "idx_bloggers_search",
}


def test_critical_indexes_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='crm' "
            "AND indexname = ANY(%s)",
            (list(EXPECTED_INDEXES),),
        )
        present = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_INDEXES - present
    assert not missing, f"Missing indexes: {missing}"


def test_rls_enabled_on_all_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='crm' "
            "AND tablename = ANY(%s) AND rowsecurity = true",
            (INFLUENCER_CRM_TABLES,),
        )
        with_rls = {row[0] for row in cur.fetchall()}
    missing = set(INFLUENCER_CRM_TABLES) - with_rls
    assert not missing, f"Tables without RLS: {missing}"


CORE_TABLES_WITH_AUDIT = ["integrations", "substitute_articles", "promo_codes", "bloggers"]


def test_audit_triggers_attached_to_core_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT event_object_table, trigger_name FROM information_schema.triggers "
            "WHERE event_object_schema='crm' AND trigger_name LIKE %s",
            ("%_audit_%",),
        )
        rows = cur.fetchall()
    by_table: dict[str, set[str]] = {}
    for tbl, trg in rows:
        by_table.setdefault(tbl, set()).add(trg)
    for tbl in CORE_TABLES_WITH_AUDIT:
        triggers = by_table.get(tbl, set())
        assert any("audit_ins" in t for t in triggers), f"{tbl}: missing audit_ins trigger"
        assert any("audit_upd" in t for t in triggers), f"{tbl}: missing audit_upd trigger"
        assert any("audit_del" in t for t in triggers), f"{tbl}: missing audit_del trigger"


def test_marketers_seed_5_rows(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM crm.marketers ORDER BY id")
        names = [row[0] for row in cur.fetchall()]
    assert names == ["Александра", "Саша", "Лиля", "Алина", "Лера"], f"Got: {names}"


def test_total_cost_generated_handles_nulls(conn):
    """Insert integration with NULL costs — total_cost must be 0, not NULL."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM crm.marketers LIMIT 1")
        marketer_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO crm.bloggers (display_handle) VALUES (%s) RETURNING id",
            ("__test_total_cost__",),
        )
        blogger_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO crm.integrations
               (blogger_id, marketer_id, publish_date, channel, ad_format, marketplace, stage)
               VALUES (%s, %s, '2026-04-01', 'instagram', 'short_video', 'wb', 'lead')
               RETURNING total_cost""",
            (blogger_id, marketer_id),
        )
        total_cost = cur.fetchone()[0]
        assert total_cost == 0, f"Expected 0, got {total_cost}"
    conn.rollback()


def test_v_blogger_totals_materialized_view(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT matviewname FROM pg_matviews WHERE schemaname='crm' "
            "AND matviewname='v_blogger_totals'"
        )
        assert cur.fetchone() is not None, "v_blogger_totals MV missing"
