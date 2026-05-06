-- =============================================================================
-- Migration 016: marketing schema (Phase 1)
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
