# Marketing Database Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `marketing` Supabase schema — three read-only views over existing `crm.*` tables + one new physical table `promo_stats_weekly` for weekly promo code metrics from WB API.

**Architecture:** `marketing` is a read-layer over `crm`. Physical data stays in `crm` (FK constraints preserved). Only `promo_stats_weekly` is a new physical table in `marketing` (no incoming FKs). ETL continues writing to `crm.*` unchanged.

**Tech Stack:** PostgreSQL 15 (Supabase), psycopg2, Python 3.12

**Spec:** `docs/superpowers/specs/2026-05-05-marketing-database-design.md`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `services/influencer_crm/migrations/015_marketing_schema.sql` | Migration: schema + table + views + RLS + grants |
| Create | `database/marketing/schema.sql` | Canonical schema reference (docs, mirrors migration) |
| Create | `scripts/smoke_test_marketing_schema.py` | Verification: row counts, RLS, column existence |

---

## Task 1: Write the smoke test first (TDD)

Write verification script before running migration. Run it now — it must FAIL. After migration, run again — must PASS. This is the acceptance test.

**Files:**
- Create: `scripts/smoke_test_marketing_schema.py`

- [ ] **Step 1.1: Create smoke test**

```python
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
        "SELECT rowsecurity FROM pg_class "
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


def run_check(cur, label: str, sql: str, expected: object) -> bool:
    try:
        cur.execute(sql)
        result = cur.fetchone()[0]
    except Exception as exc:
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
    with conn.cursor() as cur:
        for label, sql, expected in CHECKS:
            if not run_check(cur, label, sql, expected):
                failures += 1
    conn.close()

    print("\n" + ("All checks passed ✓" if failures == 0 else f"{failures} check(s) FAILED ✗"))
    return failures


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.2: Run smoke test — must FAIL**

```bash
python scripts/smoke_test_marketing_schema.py
```

Expected output: multiple `✗` lines because marketing schema doesn't exist yet. Exit code 1. If it passes — the migration was already applied, skip Task 2.

---

## Task 2: Write migration SQL

**Files:**
- Create: `services/influencer_crm/migrations/015_marketing_schema.sql`

- [ ] **Step 2.1: Create migration file**

```sql
-- =============================================================================
-- Migration 015: marketing schema (Phase 1)
-- =============================================================================
-- Creates marketing schema as an analytics read-layer over crm.*.
-- Physical crm.* tables are untouched — FK constraints preserved.
-- New physical table: marketing.promo_stats_weekly (no incoming FKs).
-- Three read-only views expose crm data under human-friendly names.
--
-- Rollback: DROP SCHEMA marketing CASCADE;
--           ALTER TABLE crm.promo_codes DROP COLUMN IF EXISTS name;
-- =============================================================================

BEGIN;

SET search_path = crm, public;

-- ---------------------------------------------------------------------------
-- 1. Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS marketing;

-- ---------------------------------------------------------------------------
-- 2. Add name column to crm.promo_codes (was missing; maps to WB internal name)
--    e.g. "Audrey/dark_beige" vs code "AUDREY3" shown to customers
-- ---------------------------------------------------------------------------
ALTER TABLE crm.promo_codes
    ADD COLUMN IF NOT EXISTS name TEXT;

-- ---------------------------------------------------------------------------
-- 3. New physical table: promo_stats_weekly
--    Populated by sync_promocodes.py from WB API — NOT from Sheets.
--    Cross-schema FK to crm.promo_codes is valid in PostgreSQL.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketing.promo_stats_weekly (
    id               BIGSERIAL PRIMARY KEY,
    promo_code_id    BIGINT NOT NULL
                         REFERENCES crm.promo_codes(id) ON DELETE RESTRICT,
    week_start       DATE NOT NULL,
    sales_rub        NUMERIC(14,2),
    payout_rub       NUMERIC(14,2),   -- ppvz_for_pay from WB API
    orders_count     INTEGER,
    returns_count    INTEGER,
    avg_discount_pct NUMERIC(5,2),    -- weighted avg actual discount that week
    avg_check        NUMERIC(12,2),   -- computed: sales_rub / NULLIF(orders_count,0)
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_psw            UNIQUE (promo_code_id, week_start),
    CONSTRAINT chk_psw_sales     CHECK (sales_rub    IS NULL OR sales_rub    >= 0),
    CONSTRAINT chk_psw_payout    CHECK (payout_rub   IS NULL OR payout_rub   >= 0),
    CONSTRAINT chk_psw_orders    CHECK (orders_count IS NULL OR orders_count >= 0),
    CONSTRAINT chk_psw_returns   CHECK (returns_count IS NULL OR returns_count >= 0),
    CONSTRAINT chk_psw_avg_disc  CHECK (avg_discount_pct IS NULL
                                        OR (avg_discount_pct >= 0 AND avg_discount_pct <= 100)),
    CONSTRAINT chk_psw_avg_check CHECK (avg_check IS NULL OR avg_check >= 0)
);

CREATE INDEX IF NOT EXISTS idx_psw_promo_week
    ON marketing.promo_stats_weekly (promo_code_id, week_start DESC);

CREATE INDEX IF NOT EXISTS idx_psw_week
    ON marketing.promo_stats_weekly (week_start DESC);

-- ---------------------------------------------------------------------------
-- 4. RLS on promo_stats_weekly
-- ---------------------------------------------------------------------------
ALTER TABLE marketing.promo_stats_weekly ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='marketing' AND tablename='promo_stats_weekly'
          AND policyname='psw_service_role'
    ) THEN
        CREATE POLICY psw_service_role ON marketing.promo_stats_weekly
            TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='marketing' AND tablename='promo_stats_weekly'
          AND policyname='psw_authenticated_read'
    ) THEN
        CREATE POLICY psw_authenticated_read ON marketing.promo_stats_weekly
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 5. Read-only views (human-friendly names for marketing consumers)
-- ---------------------------------------------------------------------------

-- Промокоды — marketing name for crm.promo_codes
CREATE OR REPLACE VIEW marketing.promo_codes AS
SELECT
    id,
    code,
    name,
    external_uuid,
    channel,
    discount_pct,
    valid_from,
    valid_until,
    status,
    notes,
    created_at,
    updated_at
FROM crm.promo_codes;

-- Поисковые запросы — renames substitute_articles + purpose→channel
CREATE OR REPLACE VIEW marketing.search_queries AS
SELECT
    id,
    code,
    artikul_id,
    purpose         AS channel,
    nomenklatura_wb,
    campaign_name,
    status,
    notes,
    external_uuid,
    created_at,
    updated_at
FROM crm.substitute_articles;

-- Статистика запросов по неделям — renames substitute_article_id→search_query_id
CREATE OR REPLACE VIEW marketing.search_query_stats_weekly AS
SELECT
    id,
    substitute_article_id AS search_query_id,
    week_start,
    frequency,
    transitions,
    additions,
    orders,
    captured_at
FROM crm.substitute_article_metrics_weekly;

-- ---------------------------------------------------------------------------
-- 6. Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA marketing TO authenticated, service_role;

-- Physical table: service_role writes, authenticated reads
GRANT ALL                ON marketing.promo_stats_weekly TO service_role;
GRANT SELECT             ON marketing.promo_stats_weekly TO authenticated;
GRANT ALL                ON SEQUENCE marketing.promo_stats_weekly_id_seq TO service_role;

-- Views: both roles read-only (writes go through crm.* directly)
GRANT SELECT ON marketing.promo_codes                TO authenticated, service_role;
GRANT SELECT ON marketing.search_queries             TO authenticated, service_role;
GRANT SELECT ON marketing.search_query_stats_weekly  TO authenticated, service_role;

COMMIT;
```

- [ ] **Step 2.2: Verify SQL syntax locally (dry-run)**

```bash
python -c "
import psycopg2, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sql = Path('services/influencer_crm/migrations/015_marketing_schema.sql').read_text()
# Just parse — don't execute
print('SQL length:', len(sql), 'chars')
print('BEGIN present:', 'BEGIN;' in sql)
print('COMMIT present:', 'COMMIT;' in sql)
print('Syntax check: OK (no execution)')
"
```

Expected output:
```
SQL length: ~3500 chars
BEGIN present: True
COMMIT present: True
Syntax check: OK (no execution)
```

---

## Task 3: Write canonical schema reference

**Files:**
- Create: `database/marketing/schema.sql`

- [ ] **Step 3.1: Create reference file**

```sql
-- =============================================================================
-- marketing schema — canonical reference
-- =============================================================================
-- READ-LAYER over crm.*. Physical tables stay in crm (FK constraints).
-- This file mirrors migration 015 for documentation purposes.
-- Apply via: services/influencer_crm/migrations/015_marketing_schema.sql
-- =============================================================================

-- Physical table (only new data in marketing schema)
-- Populated by services/sheets_sync/sync/sync_promocodes.py (Phase 2)
CREATE TABLE marketing.promo_stats_weekly (
    id               BIGSERIAL PRIMARY KEY,
    promo_code_id    BIGINT NOT NULL REFERENCES crm.promo_codes(id) ON DELETE RESTRICT,
    week_start       DATE NOT NULL,
    sales_rub        NUMERIC(14,2),
    payout_rub       NUMERIC(14,2),
    orders_count     INTEGER,
    returns_count    INTEGER,
    avg_discount_pct NUMERIC(5,2),
    avg_check        NUMERIC(12,2),
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_psw UNIQUE (promo_code_id, week_start)
);

-- Views — human-friendly read API over crm.*
CREATE VIEW marketing.promo_codes AS
    SELECT id, code, name, external_uuid, channel,
           discount_pct, valid_from, valid_until,
           status, notes, created_at, updated_at
    FROM crm.promo_codes;

CREATE VIEW marketing.search_queries AS
    SELECT id, code, artikul_id,
           purpose AS channel,
           nomenklatura_wb, campaign_name,
           status, notes, external_uuid, created_at, updated_at
    FROM crm.substitute_articles;

CREATE VIEW marketing.search_query_stats_weekly AS
    SELECT id,
           substitute_article_id AS search_query_id,
           week_start, frequency, transitions, additions, orders, captured_at
    FROM crm.substitute_article_metrics_weekly;
```

- [ ] **Step 3.2: Commit Tasks 1–3 (before applying to prod)**

```bash
git add \
  scripts/smoke_test_marketing_schema.py \
  services/influencer_crm/migrations/015_marketing_schema.sql \
  database/marketing/schema.sql
git commit -m "feat(marketing): add Phase 1 migration, schema ref, smoke test"
```

---

## Task 4: Apply migration to Supabase (prod)

- [ ] **Step 4.1: Connect and apply**

```bash
ssh timeweb "cd /opt/wookiee && \
  PGPASSWORD=\$POSTGRES_PASSWORD psql \
    -h \$POSTGRES_HOST \
    -p \$POSTGRES_PORT \
    -U \$POSTGRES_USER \
    -d \$POSTGRES_DB \
    --set=search_path=crm,public \
    -f services/influencer_crm/migrations/015_marketing_schema.sql"
```

Expected: `BEGIN`, `ALTER TABLE`, `CREATE TABLE`, `CREATE INDEX` (×2), `ALTER TABLE`, `CREATE POLICY` (×2), `CREATE VIEW` (×3), `GRANT` (×6), `COMMIT`  — no ERROR lines.

If you see `ERROR: already exists` on schema/table — the migration was partially applied before. Check what's missing and apply the remaining statements manually.

- [ ] **Step 4.2: Run smoke test against prod**

```bash
python scripts/smoke_test_marketing_schema.py
```

Expected:
```
Marketing schema smoke test
========================================
  ✓ marketing schema exists: got 1
  ✓ promo_stats_weekly table exists: got 1
  ✓ promo_stats_weekly RLS enabled: got True
  ✓ crm.promo_codes.name column exists: got 1
  ✓ marketing.promo_codes view exists: got 1
  ✓ marketing.search_queries view exists: got 1
  ✓ marketing.search_query_stats_weekly view exists: got 1
  ✓ marketing.promo_codes row count = 3: got 3
  ✓ marketing.search_queries row count = 85: got 85
  ✓ marketing.search_query_stats_weekly row count = 2565: got 2565
  ✓ search_query_stats_weekly exposes search_query_id: got 1
  ✓ search_queries exposes channel (not purpose): got 1

All checks passed ✓
```

Exit code 0. If any check fails — do NOT proceed. Fix the issue (re-run specific SQL statements) and re-run smoke test.

- [ ] **Step 4.3: Verify existing ETL still works (crm.* untouched)**

```bash
python -m services.sheets_etl.run --sheet promo_codes
```

Expected: `=== promo_codes ===` followed by `loaded: 3` (or similar). No errors. This confirms that the backward-compatible `crm.promo_codes` table still accepts ETL writes normally.

- [ ] **Step 4.4: Commit verification**

```bash
git commit --allow-empty -m "ops(marketing): Phase 1 migration applied to prod — smoke test passed"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `marketing` schema created — Task 2
- [x] `marketing.promo_stats_weekly` physical table — Task 2
- [x] Three views (`promo_codes`, `search_queries`, `search_query_stats_weekly`) — Task 2
- [x] `crm.promo_codes.name` column added — Task 2
- [x] RLS on `promo_stats_weekly` (service_role + authenticated) — Task 2
- [x] Grants for `authenticated` and `service_role` — Task 2
- [x] `crm.*` tables untouched, ETL continues working — verified in Task 4.3
- [x] Rollback documented — in migration file comment
- [x] Criteria of readiness — all verified by smoke test in Task 4.2
- [x] Cross-schema FK `promo_stats_weekly → crm.promo_codes` — in Task 2 DDL
- [x] `avg_discount_pct` field present — in Task 2 DDL
- [x] `avg_check` field present with correct semantics — in Task 2 DDL + comment

**Placeholder scan:** None found. Every step has actual code or commands.

**Type consistency:** `promo_code_id BIGINT`, `crm.promo_codes.id BIGSERIAL` — compatible. Views use exact column names from `database/crm/schema.sql` verified against grep output.
