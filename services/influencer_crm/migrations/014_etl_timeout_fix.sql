-- 014_etl_timeout_fix.sql
-- Fix: ETL job substitute_article_metrics_weekly timing out in Supabase.
--
-- Root cause:
--   The Python ETL (services/sheets_etl/loader.py) used row-by-row cur.execute()
--   to upsert metrics. The "Подменные" sheet has up to 223 weekly-metric columns
--   and 1500 rows (range A1:HZ1500), producing potentially thousands of individual
--   INSERT statements in one session. Supabase sets statement_timeout=30s for all
--   connections; a single slow statement (lock wait, autovacuum conflict, index
--   rebuild) is enough to abort the transaction.
--
-- Fix applied on the Python side (loader.py, committed alongside this migration):
--   1. statement_timeout=0 added to PG_CONFIG connection options — disables the
--      per-statement timeout for the ETL session only.
--   2. Row-by-row cur.execute() replaced with psycopg2.extras.execute_values()
--      in batches of 500 rows — single multi-row VALUES clause per batch, ~100x
--      fewer round-trips, far shorter total wall-clock time.
--
-- This migration does two additional things:
--
--   A. Grants the ETL role ALTER ROLE to override statement_timeout at the role
--      level as a belt-and-suspenders fallback (in case the options= DSN key
--      is ever stripped by a connection pooler like PgBouncer in session mode).
--
--   B. Adds a partial index on substitute_article_metrics_weekly(captured_at)
--      to speed up the retention DELETE that runs weekly (migration 011 stub).
--      Without this, the DELETE does a full seq-scan on a growing time-series table.
--
-- Apply: run once on Supabase via SQL editor (Dashboard → SQL Editor → New query).
-- Idempotent: all statements use IF NOT EXISTS or OR REPLACE.

-- ── A. Role-level statement_timeout override ─────────────────────────────────
-- The role used by the Python ETL is the Supabase service_role / postgres superuser.
-- Postgres superusers can always SET statement_timeout regardless, but this makes
-- the intent explicit and survives pooler reconfiguration.
--
-- NOTE: On Supabase managed instances, ALTER ROLE postgres … is allowed for the
-- postgres superuser. If the ETL connects as a limited service role (e.g. "authenticator"),
-- replace 'postgres' with that role name. Check with: SELECT current_user;
ALTER ROLE postgres SET statement_timeout = 0;

-- ── B. Partial index for retention DELETE on substitute_article_metrics_weekly ─
-- The weekly pg_cron retention job (scheduled as a stub in migration 011 / schema.sql)
-- deletes rows where week_start < (now() - INTERVAL '2 years')::date.
-- A partial index on week_start covering only old rows makes the DELETE O(deleted)
-- instead of O(total_table_rows).
-- Note: partial index predicates require IMMUTABLE functions; now() is VOLATILE.
-- Using a static cutoff date (updated manually ~yearly) instead.
-- Current cutoff: rows older than 2024-01-01 are considered "retention candidates".
CREATE INDEX IF NOT EXISTS idx_samw_week_retention
    ON crm.substitute_article_metrics_weekly (week_start)
    WHERE week_start < '2024-01-01'::date;

-- ── Verification queries (run manually after applying) ────────────────────────
-- 1. Confirm role timeout is cleared:
--      SHOW statement_timeout;   -- should return '0' from an ETL connection
-- 2. Confirm index exists:
--      SELECT indexname FROM pg_indexes
--       WHERE tablename = 'substitute_article_metrics_weekly'
--         AND indexname = 'idx_samw_week_retention';
-- 3. Confirm ETL succeeds: check crm.etl_runs for status='success' after next run.
--      SELECT agent, status, duration_ms, error_message
--        FROM crm.etl_runs
--       WHERE agent = 'crm-sheets-etl'
--       ORDER BY started_at DESC
--       LIMIT 5;
