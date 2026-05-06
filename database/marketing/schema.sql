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
