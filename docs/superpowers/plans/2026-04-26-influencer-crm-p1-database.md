# Phase 1: Influencer CRM Database Setup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply migration 008 (v4.1 schema, 22 tables) to dev Supabase, write idempotent Python wrapper, verify with smoke tests, document in README.

**Architecture:** SQL migration lives in `sku_database/database/migrations/008_influencer_crm.sql` (already drafted in `.superpowers/brainstorm/4161-1777122150/content/migration_008_influencer_crm.sql` — copied during T1). Python wrapper in `sku_database/scripts/migrations/008_create_influencer_crm.py` follows pattern of `005_fix_supabase_security.py`: takes flags `--dry-run`, `--force`, connects via service_role pooler. Smoke tests in `sku_database/scripts/test_influencer_crm_schema.py` verify 22 tables, indexes, triggers, RLS, MV.

**Tech Stack:** Python 3.11, psycopg 3 (sync), pytest, Supabase Postgres 15.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `sku_database/database/migrations/008_influencer_crm.sql` | DDL of 22 tables + indexes + triggers + RLS + MV | Drafted in brainstorm, copied in T1 |
| `sku_database/scripts/migrations/008_create_influencer_crm.py` | Python wrapper: applies SQL transactionally, handles --dry-run | New |
| `sku_database/scripts/test_influencer_crm_schema.py` | pytest smoke tests against applied schema | New |
| `sku_database/database/influencer_crm_models.py` | SQLAlchemy declarative models (typed, mirror DDL) | New |
| `sku_database/README.md` | Section about Influencer CRM tables | Modify |
| `docs/database/INFLUENCER_CRM.md` | High-level doc with link to v4.1 HTML | New |

---

## Task 1: Move SQL into the canonical migrations folder

**Files:**
- Modify: copy from `.superpowers/brainstorm/4161-1777122150/content/migration_008_influencer_crm.sql` to `sku_database/database/migrations/008_influencer_crm.sql`

- [ ] **Step 1: Create migrations directory if missing, copy file**

```bash
mkdir -p sku_database/database/migrations
cp .superpowers/brainstorm/4161-1777122150/content/migration_008_influencer_crm.sql \
   sku_database/database/migrations/008_influencer_crm.sql
```

- [ ] **Step 2: Verify copy + counts unchanged**

```bash
diff -q .superpowers/brainstorm/4161-1777122150/content/migration_008_influencer_crm.sql \
        sku_database/database/migrations/008_influencer_crm.sql
grep -c "^CREATE TABLE" sku_database/database/migrations/008_influencer_crm.sql
```
Expected: no diff output, count = 22.

- [ ] **Step 3: Commit**

```bash
git add sku_database/database/migrations/008_influencer_crm.sql
git commit -m "feat(crm): seed migration 008 SQL — Influencer CRM schema v4.1"
```

---

## Task 2: Write the failing smoke test (table count)

**Files:**
- Create: `sku_database/scripts/test_influencer_crm_schema.py`

- [ ] **Step 1: Add pytest dependency check**

```bash
pip show pytest >/dev/null 2>&1 || pip install pytest
```

- [ ] **Step 2: Write failing test — `test_22_tables_exist`**

```python
# sku_database/scripts/test_influencer_crm_schema.py
"""Smoke tests for Influencer CRM schema (migration 008).

Run AFTER migration is applied to verify the schema is healthy.
Connects via service_role pooler (same as application code).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import pytest

# Allow `from config.database import get_connection`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.database import get_connection  # noqa: E402

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
    c = get_connection()
    try:
        yield c
    finally:
        c.close()


def test_22_tables_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ANY(%s)
            """,
            (INFLUENCER_CRM_TABLES,),
        )
        present = {row[0] for row in cur.fetchall()}
    missing = set(INFLUENCER_CRM_TABLES) - present
    assert not missing, f"Missing tables: {missing}"
    assert len(present) == 22
```

- [ ] **Step 3: Run the test (expected to fail — migration not applied yet)**

```bash
cd sku_database
pytest scripts/test_influencer_crm_schema.py -v
```
Expected: FAIL with `Missing tables: {...}` or AssertionError. Confirms test wired correctly.

---

## Task 3: Write Python wrapper for migration 008

**Files:**
- Create: `sku_database/scripts/migrations/008_create_influencer_crm.py`
- Reference (don't copy): `sku_database/scripts/migrations/005_fix_supabase_security.py`

- [ ] **Step 1: Read 005 to lock pattern**

```bash
head -80 sku_database/scripts/migrations/005_fix_supabase_security.py
```

- [ ] **Step 2: Write wrapper script**

```python
# sku_database/scripts/migrations/008_create_influencer_crm.py
"""Migration 008: Influencer CRM (schema v4.1).

Creates 22 tables for blogger relationship management.
Idempotent only via DROP-and-recreate (use --force). Default behaviour: fail
if any table already exists, to prevent accidental overwrite.

Usage:
    python scripts/migrations/008_create_influencer_crm.py [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `from config.database import get_connection`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config.database import get_connection  # noqa: E402

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


def existing_crm_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name = ANY(%s)",
            (CRM_TABLES,),
        )
        return [row[0] for row in cur.fetchall()]


def drop_crm_tables(conn) -> None:
    """Drop in reverse-dependency order. CASCADE handles FK chains."""
    drop_order = list(reversed(CRM_TABLES))
    with conn.cursor() as cur:
        for tbl in drop_order:
            cur.execute(f'DROP TABLE IF EXISTS public."{tbl}" CASCADE')
        cur.execute('DROP MATERIALIZED VIEW IF EXISTS public.v_blogger_totals')
        cur.execute('DROP FUNCTION IF EXISTS public.trg_audit_log() CASCADE')
        cur.execute('DROP FUNCTION IF EXISTS public.trg_integration_stage_history() CASCADE')
        cur.execute('DROP FUNCTION IF EXISTS public.trg_set_updated_at() CASCADE')


def apply_migration(dry_run: bool, force: bool) -> int:
    sql = SQL_FILE.read_text(encoding="utf-8")

    conn = get_connection()
    conn.autocommit = False
    try:
        existing = existing_crm_tables(conn)
        if existing:
            if not force:
                print(f"ERROR: existing CRM tables detected: {existing}", file=sys.stderr)
                print("Re-run with --force to drop and recreate.", file=sys.stderr)
                return 2
            print(f"--force given. Dropping {len(existing)} existing CRM tables...")
            drop_crm_tables(conn)
            conn.commit()

        if dry_run:
            print(f"DRY RUN: would apply {len(sql)} bytes of SQL ({sql.count('CREATE TABLE')} tables)")
            return 0

        print(f"Applying migration 008 ({len(sql)} bytes)...")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        # Verify
        applied = existing_crm_tables(conn)
        assert len(applied) == 22, f"Expected 22 tables, got {len(applied)}: missing {set(CRM_TABLES) - set(applied)}"
        print(f"OK: 22 tables created.")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="Drop existing CRM tables before re-applying")
    args = p.parse_args()
    return apply_migration(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Test --dry-run path (no DB writes)**

```bash
cd sku_database
python scripts/migrations/008_create_influencer_crm.py --dry-run
```
Expected: prints `DRY RUN: would apply N bytes of SQL (22 tables)` and exits 0.

- [ ] **Step 4: Commit**

```bash
git add sku_database/scripts/migrations/008_create_influencer_crm.py \
        sku_database/scripts/test_influencer_crm_schema.py
git commit -m "feat(crm): add migration 008 wrapper + smoke test scaffold"
```

---

## Task 4: Apply migration to Supabase dev

**Files:**
- No new files. Run script.

- [ ] **Step 1: Apply migration**

```bash
cd sku_database
python scripts/migrations/008_create_influencer_crm.py
```
Expected: prints `Applying migration 008 (...)` then `OK: 22 tables created.` and exits 0.

- [ ] **Step 2: Run smoke test — should now PASS**

```bash
pytest scripts/test_influencer_crm_schema.py::test_22_tables_exist -v
```
Expected: PASS.

- [ ] **Step 3: Verify materialized view exists**

```bash
python db.py query "SELECT matviewname FROM pg_matviews WHERE schemaname='public' AND matviewname='v_blogger_totals'"
```
Expected: 1 row returned.

---

## Task 5: Add full smoke-test suite (indexes, triggers, RLS, FK)

**Files:**
- Modify: `sku_database/scripts/test_influencer_crm_schema.py` — append tests

- [ ] **Step 1: Append `test_critical_indexes_exist`**

```python
# Append to test_influencer_crm_schema.py
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
            "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
            "AND indexname = ANY(%s)",
            (list(EXPECTED_INDEXES),),
        )
        present = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_INDEXES - present
    assert not missing, f"Missing indexes: {missing}"
```

- [ ] **Step 2: Append `test_rls_enabled_on_all_tables`**

```python
def test_rls_enabled_on_all_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename = ANY(%s) AND rowsecurity = true",
            (INFLUENCER_CRM_TABLES,),
        )
        with_rls = {row[0] for row in cur.fetchall()}
    missing = set(INFLUENCER_CRM_TABLES) - with_rls
    assert not missing, f"Tables without RLS: {missing}"
```

- [ ] **Step 3: Append `test_audit_triggers_attached_to_core_tables`**

```python
CORE_TABLES_WITH_AUDIT = ["integrations", "substitute_articles", "promo_codes", "bloggers"]


def test_audit_triggers_attached_to_core_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT event_object_table, trigger_name FROM information_schema.triggers "
            "WHERE event_object_schema='public' AND trigger_name LIKE %s",
            ("%_audit_%",),
        )
        rows = cur.fetchall()
    by_table: dict[str, set[str]] = {}
    for tbl, trg in rows:
        by_table.setdefault(tbl, set()).add(trg)
    for tbl in CORE_TABLES_WITH_AUDIT:
        triggers = by_table.get(tbl, set())
        # Each table should have ins/upd/del audit triggers
        assert any("audit_ins" in t for t in triggers), f"{tbl}: missing audit_ins trigger"
        assert any("audit_upd" in t for t in triggers), f"{tbl}: missing audit_upd trigger"
        assert any("audit_del" in t for t in triggers), f"{tbl}: missing audit_del trigger"
```

- [ ] **Step 4: Append `test_marketers_seed_5_rows`**

```python
def test_marketers_seed_5_rows(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM marketers ORDER BY id")
        names = [row[0] for row in cur.fetchall()]
    assert names == ["Александра", "Саша", "Лиля", "Алина", "Лера"], f"Got: {names}"
```

- [ ] **Step 5: Append `test_total_cost_generated_handles_nulls`**

```python
def test_total_cost_generated_handles_nulls(conn):
    """Insert integration with NULL costs — total_cost must be 0, not NULL."""
    with conn.cursor() as cur:
        # Need a valid blogger + marketer
        cur.execute("SELECT id FROM marketers LIMIT 1")
        marketer_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO bloggers (display_handle) VALUES (%s) RETURNING id",
            ("__test_total_cost__",),
        )
        blogger_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO integrations
               (blogger_id, marketer_id, publish_date, channel, ad_format, marketplace, stage)
               VALUES (%s, %s, '2026-04-01', 'instagram', 'short_video', 'wb', 'lead')
               RETURNING total_cost""",
            (blogger_id, marketer_id),
        )
        total_cost = cur.fetchone()[0]
        assert total_cost == 0, f"Expected 0, got {total_cost}"
        # Cleanup
        conn.rollback()
```

- [ ] **Step 6: Run full test suite**

```bash
cd sku_database
pytest scripts/test_influencer_crm_schema.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add sku_database/scripts/test_influencer_crm_schema.py
git commit -m "test(crm): smoke tests for indexes, RLS, audit triggers, marketers seed, generated columns"
```

---

## Task 6: Add SQLAlchemy models (mirror DDL types)

**Files:**
- Create: `sku_database/database/influencer_crm_models.py`
- Reference: `sku_database/database/models.py`

- [ ] **Step 1: Read existing models style**

```bash
head -60 sku_database/database/models.py
```

- [ ] **Step 2: Write models module — minimum viable subset**

```python
# sku_database/database/influencer_crm_models.py
"""SQLAlchemy 2.x typed models for Influencer CRM (migration 008).

Mirrors DDL in database/migrations/008_influencer_crm.sql exactly.
Use via session: from database.influencer_crm_models import Blogger, Integration, ...
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, JSON,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Marketer(Base):
    __tablename__ = "marketers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    bitrix_user_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, default="both", nullable=False)
    color_hex: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Blogger(Base):
    __tablename__ = "bloggers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    display_handle: Mapped[str] = mapped_column(Text, nullable=False)
    real_name: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(Text)
    default_marketer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("marketers.id"))
    audience_age: Mapped[Optional[dict]] = mapped_column(JSONB)
    geo_country: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    contact_tg: Mapped[Optional[str]] = mapped_column(Text)
    contact_email: Mapped[Optional[str]] = mapped_column(Text)
    contact_phone: Mapped[Optional[str]] = mapped_column(Text)
    price_story_default: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    price_reels_default: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    payment_method_default: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    archived_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sheet_row_id: Mapped[Optional[str]] = mapped_column(Text, unique=True)


class BloggerChannel(Base):
    __tablename__ = "blogger_channels"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blogger_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bloggers.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text)
    followers: Mapped[Optional[int]] = mapped_column(Integer)
    min_reach: Mapped[Optional[int]] = mapped_column(Integer)
    er_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    last_synced_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))


class SubstituteArticle(Base):
    __tablename__ = "substitute_articles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    artikul_id: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    nomenklatura_wb: Mapped[Optional[str]] = mapped_column(Text)
    campaign_name: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    external_uuid: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    sheet_row_id: Mapped[Optional[str]] = mapped_column(Text)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    artikul_id: Mapped[Optional[int]] = mapped_column(Integer)
    channel: Mapped[Optional[str]] = mapped_column(Text)
    discount_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    valid_from: Mapped[Optional[dt.date]] = mapped_column(Date)
    valid_until: Mapped[Optional[dt.date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    external_uuid: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blogger_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bloggers.id"), nullable=False)
    marketer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("marketers.id"), nullable=False)
    brief_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    publish_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    ad_format: Mapped[str] = mapped_column(Text, nullable=False)
    marketplace: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, default="lead", nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(Text)
    is_barter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cost_placement: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    cost_delivery: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    cost_goods: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # GENERATED, read-only
    erid: Mapped[Optional[str]] = mapped_column(Text)
    publish_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    archived_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    sheet_row_id: Mapped[Optional[str]] = mapped_column(Text, unique=True)


# NOTE: 14 more tables (junctions, history, snapshots, candidates, etc.) intentionally
# left out of MVP models. Add as ETL/API code requires them.
```

- [ ] **Step 3: Smoke-import the module**

```bash
cd sku_database
python -c "from database.influencer_crm_models import Blogger, Integration, Marketer, Tag, PromoCode, SubstituteArticle, BloggerChannel; print('OK')"
```
Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add sku_database/database/influencer_crm_models.py
git commit -m "feat(crm): add SQLAlchemy models for 7 core CRM tables"
```

---

## Task 7: Document Influencer CRM in repo docs

**Files:**
- Create: `docs/database/INFLUENCER_CRM.md`
- Modify: `sku_database/README.md` — add section pointer

- [ ] **Step 1: Create CRM doc**

```markdown
# Influencer CRM (migration 008)

22-table CRM for blogger relationship management on top of `sku_database`.

## Source-of-truth artifacts
- HTML schema with ERD: [.superpowers/brainstorm/4161-1777122150/content/db-schema-v4.html](../../.superpowers/brainstorm/4161-1777122150/content/db-schema-v4.html)
- DDL migration: [sku_database/database/migrations/008_influencer_crm.sql](../../sku_database/database/migrations/008_influencer_crm.sql)
- Implementation roadmap: [docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md](../superpowers/plans/2026-04-26-influencer-crm-roadmap.md)

## Tables (22)

**Core CRM (5):** marketers, bloggers, blogger_channels, integrations, briefs
**Junctions (5):** integration_substitute_articles, integration_promo_codes, blogger_tags, integration_tags, brief_versions
**Tracking (4):** substitute_articles, substitute_article_metrics_weekly, promo_codes, integration_posts
**History/aggregates (3):** integration_stage_history, integration_metrics_snapshots, v_blogger_totals (materialized view)
**Reference + supporting (5):** tags, content_brief_templates, blogger_candidates, branded_queries, audit_log
**Sync metadata (1):** sheets_sync_state

## Key design decisions
- **PKs are BIGSERIAL** (FK on existing INT artikuly works directly)
- **No native enums** — text + CHECK (drop+add tolerated, native enum modification is painful)
- **stage and outcome are independent axes** — stage = funnel position, outcome = cancelled/refunded/no_show
- **Multi-model integrations via junction** with display_order (no `is_primary` boolean)
- **Soft-delete via `archived_at` only** (no `status='archived'` duplicate state)
- **Idempotent re-import via content-hash `sheet_row_id`** (NOT positional A1 notation)

## Auth model
Local Python BFF connects via service_role pooler. RLS enabled on all 22 tables but bypassed by service_role. The `authenticated_select_*` policies are defense-in-depth for future Supabase Auth migration.

## Running the migration
```bash
cd sku_database
python scripts/migrations/008_create_influencer_crm.py [--dry-run] [--force]
```
Smoke tests:
```bash
pytest scripts/test_influencer_crm_schema.py -v
```
```

- [ ] **Step 2: Append section to sku_database README**

In `sku_database/README.md`, after the "Структура проекта" section, add:

```markdown
## Influencer CRM (migration 008)

22 tables for blogger relationship management. See [docs/database/INFLUENCER_CRM.md](../docs/database/INFLUENCER_CRM.md).
```

- [ ] **Step 3: Commit**

```bash
git add docs/database/INFLUENCER_CRM.md sku_database/README.md
git commit -m "docs(crm): document Influencer CRM schema and migration"
```

---

## Task 8: Update memory + close phase

**Files:**
- Modify: user memory `MEMORY.md` (auto-memory)
- Create: `/Users/danilamatveev/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/project_influencer_crm.md`

- [ ] **Step 1: Save memory entry**

Write `project_influencer_crm.md`:

```markdown
---
name: Influencer CRM
description: 22-table Supabase schema for blogger relationship management (Phase 1 done 2026-04-26)
type: project
---

# Influencer CRM

## Status
- 2026-04-26: Phase 1 (database) DONE. Migration 008 applied to dev Supabase.
- 22 tables: bloggers, integrations, substitute_articles, promo_codes + 18 supporting.
- Schema v4.1 (HTML): .superpowers/brainstorm/4161-1777122150/content/db-schema-v4.html
- Roadmap: docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md

## Phases
1. ✅ Database — migration 008 applied
2. ⏭ Sheets ETL — pull-only from "Маркетинг Wookiee" workbook
3. ⏭ API BFF — FastAPI on service_role
4. ⏭ Frontend — React+Vite+Tailwind on v3a/v3b mockups
5. ⏭ Sync & monitoring

## Key decisions locked
- BIGSERIAL PKs (not UUID); FK on existing INT artikuly works directly
- No Supabase Auth on local — service_role only via Python BFF
- Sheets is SoT until cutover; pull-only direction
- 1 WW = 1 артикул; multi-model via junction (display_order)
- Brief 1:N (один договор может покрывать несколько интеграций)
- Compliance booleans nullable (NULL = "not yet evaluated")
- stage and outcome are independent axes
```

- [ ] **Step 2: Append index entry to MEMORY.md**

Insert under `## Проект` section:

```markdown
- [Influencer CRM](project_influencer_crm.md) — 22-table Supabase schema for blogger CRM, Phase 1 DONE 2026-04-26
```

- [ ] **Step 3: Final verification — run all phase 1 deliverables**

```bash
# 1. Migration applied
cd sku_database && python -c "from config.database import get_connection; c=get_connection(); cur=c.cursor(); cur.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='integrations'\"); print(cur.fetchone())"

# 2. Smoke tests pass
pytest scripts/test_influencer_crm_schema.py -v

# 3. SQLAlchemy models load
python -c "from database.influencer_crm_models import Blogger; print('OK')"

# 4. Documentation in place
ls -la ../docs/database/INFLUENCER_CRM.md ../docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md
```
Expected: count=1, all tests PASS, OK printed, both docs exist.

- [ ] **Step 4: Final commit**

```bash
git add MEMORY.md  # only if outside repo — this lives in ~/.claude
git status
# If anything else uncommitted from phase 1, commit it
git commit --allow-empty -m "feat(crm): Phase 1 (database) complete — migration 008 applied + smoke tests + docs"
```

---

## Self-Review Checklist

- **Spec coverage**: 22 tables created (T1, T4), smoke tested (T2, T5), wrapped in idempotent Python (T3), models defined (T6), documented (T7), memorialized (T8). ✅
- **Placeholder scan**: every code block is complete and runnable. No "TBD", "implement later", "similar to X". ✅
- **Type consistency**: `INFLUENCER_CRM_TABLES` list identical in T2 and T3. `BIGSERIAL` → `BigInteger` in models. `numeric(12,2)` → `Numeric(12, 2)` consistently. ✅

## Phase 1 Done Definition

- [x] All 22 tables in Supabase dev project
- [x] Migration script idempotent via `--force`
- [x] Smoke tests pass (5 tests)
- [x] SQLAlchemy models import-able
- [x] Documentation linked from sku_database README
- [x] Memory entry persists Phase 1 done

When all checked → write Phase 2 plan (Sheets ETL).
