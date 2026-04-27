-- =============================================================================
-- Migration 008: Influencer CRM (schema v4.1)
-- =============================================================================
-- Creates 22 tables (15 core CRM + 7 supporting) for blogger relationship
-- management on top of sku_database. Schema decisions in db-schema-v4.html.
-- v4.1 deltas (from codex-arch-review): C1-C5 + W1, W3, W7, W8, W10 (see HTML).
-- Apply via: scripts/migrations/008_create_influencer_crm.py (wraps in transaction)
--
-- Conventions:
--   - BIGSERIAL PKs (DEC-1)
--   - text + CHECK instead of native enum (DEC-5, M9)
--   - All timestamps timestamptz default now()
--   - Soft-delete via archived_at (canonical) where applicable; status='archived' removed
--   - RLS enabled on every table; service_role full, authenticated read-only, anon revoked
--   - Foreign keys ON DELETE RESTRICT (no silent data loss)
--
-- IDEMPOTENT IMPORT POLICY (sheet_row_id):
--   sheet_row_id MUST be a content-stable hash (not positional A1-notation).
--   ETL computes MD5(handle || publish_date || channel) per Sheets row.
--   Insertion rule: ON CONFLICT (sheet_row_id) DO UPDATE on safe fields only;
--   never DO UPDATE blindly — that masks data drift in source rows.
-- =============================================================================

BEGIN;

-- Influencer CRM lives in its own schema for logical isolation.
-- Cross-schema FK to public.artikuly works via search_path resolution
-- (crm first; falls through to public for upstream tables).
CREATE SCHEMA IF NOT EXISTS crm;
SET search_path = crm, public;

-- -----------------------------------------------------------------------------
-- Pre-flight: required upstream tables must exist in public schema
-- -----------------------------------------------------------------------------
DO $$
DECLARE missing TEXT[] := ARRAY[]::TEXT[];
        t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['artikuly','modeli','modeli_osnova','cveta'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=t
        ) THEN
            missing := array_append(missing, t);
        END IF;
    END LOOP;
    IF array_length(missing, 1) > 0 THEN
        RAISE EXCEPTION 'Migration 008 pre-flight failed: missing upstream tables in public schema: %', missing;
    END IF;
END$$;

-- -----------------------------------------------------------------------------
-- Extensions (idempotent)
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =============================================================================
-- 1. marketers (reference)
-- =============================================================================
CREATE TABLE marketers (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    bitrix_user_id  INTEGER,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_marketers_name UNIQUE (name),
    CONSTRAINT uq_marketers_bitrix_user_id UNIQUE (bitrix_user_id)
);

INSERT INTO marketers (name) VALUES
    ('Александра'),
    ('Саша'),
    ('Лиля'),
    ('Алина'),
    ('Лера');


-- =============================================================================
-- 2. tags (reference for both bloggers and integrations)
-- =============================================================================
CREATE TABLE tags (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'both',
    color_hex   TEXT,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_tags_kind CHECK (kind IN ('blogger', 'integration', 'both')),
    CONSTRAINT chk_tags_color_hex CHECK (color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE UNIQUE INDEX uq_tags_name ON tags (LOWER(name));

INSERT INTO tags (name, kind, color_hex) VALUES
    ('lifestyle',   'both', '#8B5CF6'),
    ('стилист',     'both', '#EC4899'),
    ('обзоры',      'both', '#F97316'),
    ('fashion',     'both', '#3B82F6'),
    ('beauty',      'both', '#22C55E'),
    ('family',      'both', '#F59E0B'),
    ('plus_size',   'both', '#14B8A6');


-- =============================================================================
-- 3. bloggers
-- =============================================================================
CREATE TABLE bloggers (
    id                     BIGSERIAL PRIMARY KEY,
    display_handle         TEXT NOT NULL,
    real_name              TEXT,
    city                   TEXT,
    default_marketer_id    BIGINT REFERENCES marketers(id) ON DELETE SET NULL,
    audience_age           JSONB,
    geo_country            TEXT[],
    contact_tg             TEXT,
    contact_email          TEXT,
    contact_phone          TEXT,
    price_story_default    NUMERIC(12,2),
    price_reels_default    NUMERIC(12,2),
    payment_method_default TEXT,
    notes                  TEXT,
    status                 TEXT NOT NULL DEFAULT 'active',
    archived_at            TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    sheet_row_id           TEXT,
    -- W3 (codex-arch-review): 'archived' removed from CHECK; soft-delete is archived_at IS NOT NULL.
    CONSTRAINT chk_bloggers_status CHECK (status IN ('active','in_progress','new','paused')),
    CONSTRAINT chk_bloggers_payment CHECK (
        payment_method_default IS NULL OR
        payment_method_default IN ('sbp_card','samozanyaty','ip','barter','other')
    ),
    CONSTRAINT chk_bloggers_prices CHECK (
        COALESCE(price_story_default, 0) >= 0
        AND COALESCE(price_reels_default, 0) >= 0
    ),
    CONSTRAINT uq_bloggers_sheet_row_id UNIQUE (sheet_row_id)
);

CREATE INDEX idx_bloggers_marketer ON bloggers (default_marketer_id) WHERE archived_at IS NULL;
CREATE INDEX idx_bloggers_status ON bloggers (status) WHERE archived_at IS NULL;

-- Full-text search across display_handle + real_name + notes.
-- Expression GIN index avoids the STORED-generated-column requirement that
-- the expression be IMMUTABLE (to_tsvector is STABLE, not IMMUTABLE).
CREATE INDEX idx_bloggers_search ON bloggers
    USING gin (
        to_tsvector('russian',
            coalesce(display_handle,'') || ' ' ||
            coalesce(real_name,'') || ' ' ||
            coalesce(notes,'')
        )
    );


-- =============================================================================
-- 4. blogger_channels (N social channels per blogger)
-- =============================================================================
CREATE TABLE blogger_channels (
    id              BIGSERIAL PRIMARY KEY,
    blogger_id      BIGINT NOT NULL REFERENCES bloggers(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,
    handle          TEXT NOT NULL,
    url             TEXT,
    followers       INTEGER,
    min_reach       INTEGER,
    er_pct          NUMERIC(5,2),
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_channels_channel CHECK (channel IN ('instagram','youtube','tiktok','telegram','vk','rutube','other')),
    CONSTRAINT chk_channels_followers CHECK (followers IS NULL OR followers >= 0),
    CONSTRAINT chk_channels_er CHECK (er_pct IS NULL OR (er_pct >= 0 AND er_pct <= 100))
);

CREATE UNIQUE INDEX uq_blogger_channels_handle ON blogger_channels (channel, LOWER(handle));
CREATE INDEX idx_blogger_channels_blogger ON blogger_channels (blogger_id);


-- =============================================================================
-- 5. blogger_tags (M:N junction)
-- =============================================================================
CREATE TABLE blogger_tags (
    blogger_id  BIGINT NOT NULL REFERENCES bloggers(id) ON DELETE CASCADE,
    tag_id      BIGINT NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (blogger_id, tag_id)
);

CREATE INDEX idx_blogger_tags_tag ON blogger_tags (tag_id);


-- =============================================================================
-- 6. content_brief_templates  (templates for ТЗ by channel/format)
-- =============================================================================
CREATE TABLE content_brief_templates (
    id          BIGSERIAL PRIMARY KEY,
    channel     TEXT NOT NULL,
    ad_format   TEXT NOT NULL,
    title       TEXT NOT NULL,
    content     JSONB NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    is_current  BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cbt_channel CHECK (channel IN ('instagram','youtube','tiktok','telegram','vk','rutube','other','any')),
    CONSTRAINT chk_cbt_ad_format CHECK (ad_format IN ('short_video','long_video','image_post','text_post','live_stream','story','integration','long_post','any'))
);

-- Only one current template per (channel, ad_format)
CREATE UNIQUE INDEX uq_cbt_current
    ON content_brief_templates (channel, ad_format)
    WHERE is_current;


-- =============================================================================
-- 7. briefs + brief_versions
-- =============================================================================
CREATE TABLE briefs (
    id              BIGSERIAL PRIMARY KEY,
    template_id     BIGINT REFERENCES content_brief_templates(id) ON DELETE SET NULL,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    current_version INTEGER NOT NULL DEFAULT 1,
    deadline_draft  DATE,
    signed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_briefs_status CHECK (status IN ('draft','review','signed','finished','cancelled'))
);

CREATE TABLE brief_versions (
    id          BIGSERIAL PRIMARY KEY,
    brief_id    BIGINT NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    content     JSONB,
    file_url    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  BIGINT REFERENCES marketers(id) ON DELETE SET NULL,
    CONSTRAINT uq_brief_versions UNIQUE (brief_id, version)
);

CREATE INDEX idx_brief_versions_brief ON brief_versions (brief_id, version DESC);


-- =============================================================================
-- 8. substitute_articles (WW codes for traffic tracking)
-- =============================================================================
CREATE TABLE substitute_articles (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL,
    artikul_id      INTEGER NOT NULL,  -- FK to existing sku_database.artikuly(id)
    purpose         TEXT NOT NULL,
    nomenklatura_wb TEXT,
    campaign_name   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    external_uuid   UUID,
    sheet_row_id    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sub_purpose CHECK (purpose IN ('creators','adblogger','yandex','vk_target','other')),
    CONSTRAINT chk_sub_status CHECK (status IN ('active','paused','archived')),
    CONSTRAINT uq_sub_code UNIQUE (code),
    CONSTRAINT uq_sub_external UNIQUE (external_uuid),
    CONSTRAINT uq_sub_sheet_row UNIQUE (sheet_row_id),
    CONSTRAINT fk_sub_artikul FOREIGN KEY (artikul_id) REFERENCES artikuly(id) ON DELETE RESTRICT
);

CREATE INDEX idx_sub_artikul ON substitute_articles (artikul_id);
CREATE INDEX idx_sub_status ON substitute_articles (status) WHERE status = 'active';
CREATE UNIQUE INDEX uq_sub_code_lower ON substitute_articles (LOWER(code));


-- =============================================================================
-- 9. substitute_article_metrics_weekly (vertical normalised from "Подменные" 223 cols)
-- =============================================================================
CREATE TABLE substitute_article_metrics_weekly (
    id                      BIGSERIAL PRIMARY KEY,
    substitute_article_id   BIGINT NOT NULL REFERENCES substitute_articles(id) ON DELETE CASCADE,
    week_start              DATE NOT NULL,
    frequency               INTEGER,
    transitions             INTEGER,
    additions               INTEGER,
    orders                  INTEGER,
    captured_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_samw UNIQUE (substitute_article_id, week_start),
    CONSTRAINT chk_samw_metrics CHECK (
        COALESCE(frequency, 0)   >= 0 AND
        COALESCE(transitions, 0) >= 0 AND
        COALESCE(additions, 0)   >= 0 AND
        COALESCE(orders, 0)      >= 0
    )
);

CREATE INDEX idx_samw_week ON substitute_article_metrics_weekly (week_start DESC);
CREATE INDEX idx_samw_sub_week ON substitute_article_metrics_weekly (substitute_article_id, week_start DESC);


-- =============================================================================
-- 10. promo_codes (mirrored to substitute_articles)
-- =============================================================================
-- C3 (codex-arch-review): artikul_id intentionally NULLABLE (asymmetric vs substitute_articles).
-- Rationale: promo codes can be store-wide (e.g., "OOOCORP25" — corporate discount on any SKU).
-- Reports MUST handle NULL artikul_id explicitly; do not silent-exclude via INNER JOIN.
CREATE TABLE promo_codes (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL,
    artikul_id      INTEGER REFERENCES artikuly(id) ON DELETE RESTRICT,  -- NULL = store-wide
    channel         TEXT,
    discount_pct    NUMERIC(5,2),
    discount_amount NUMERIC(12,2),
    valid_from      DATE,
    valid_until     DATE,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    external_uuid   UUID,
    sheet_row_id    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_promo_status CHECK (status IN ('active','paused','expired','archived')),
    CONSTRAINT chk_promo_discount CHECK (
        (discount_pct IS NOT NULL AND discount_amount IS NULL) OR
        (discount_pct IS NULL AND discount_amount IS NOT NULL) OR
        (discount_pct IS NULL AND discount_amount IS NULL)
    ),
    CONSTRAINT chk_promo_pct_range CHECK (discount_pct IS NULL OR (discount_pct >= 0 AND discount_pct <= 100)),
    CONSTRAINT chk_promo_amount CHECK (discount_amount IS NULL OR discount_amount >= 0),
    CONSTRAINT chk_promo_dates CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CONSTRAINT uq_promo_code UNIQUE (code),
    CONSTRAINT uq_promo_external UNIQUE (external_uuid),
    CONSTRAINT uq_promo_sheet_row UNIQUE (sheet_row_id)
);

CREATE INDEX idx_promo_artikul ON promo_codes (artikul_id) WHERE artikul_id IS NOT NULL;
CREATE INDEX idx_promo_status ON promo_codes (status) WHERE status = 'active';
CREATE INDEX idx_promo_valid ON promo_codes (valid_from, valid_until) WHERE status = 'active';


-- =============================================================================
-- 11. integrations (CORE TABLE)
-- =============================================================================
CREATE TABLE integrations (
    id                       BIGSERIAL PRIMARY KEY,
    blogger_id               BIGINT NOT NULL REFERENCES bloggers(id) ON DELETE RESTRICT,
    marketer_id              BIGINT NOT NULL REFERENCES marketers(id) ON DELETE RESTRICT,
    brief_id                 BIGINT REFERENCES briefs(id) ON DELETE SET NULL,
    publish_date             DATE NOT NULL,
    channel                  TEXT NOT NULL,
    ad_format                TEXT NOT NULL,
    marketplace              TEXT NOT NULL,
    stage                    TEXT NOT NULL DEFAULT 'lead',
    outcome                  TEXT,
    cancelled_reason         TEXT,
    rescheduled_from_date    DATE,
    reschedule_count         INTEGER NOT NULL DEFAULT 0,
    is_barter                BOOLEAN NOT NULL DEFAULT false,
    cost_placement           NUMERIC(12,2),
    cost_delivery            NUMERIC(12,2),
    cost_goods               NUMERIC(12,2),
    total_cost               NUMERIC(12,2)
        GENERATED ALWAYS AS (
            COALESCE(cost_placement, 0) +
            COALESCE(cost_delivery, 0) +
            COALESCE(cost_goods, 0)
        ) STORED,
    payment_method           TEXT,
    erid                     TEXT,
    contract_url             TEXT,
    post_url                 TEXT,
    screen_url               TEXT,
    tz_url                   TEXT,
    post_content             TEXT,
    analysis                 TEXT,
    recommended_models       TEXT,
    plan_views               INTEGER,
    plan_ctr                 NUMERIC(5,2),
    plan_clicks              INTEGER,
    plan_cpc                 NUMERIC(10,2),
    plan_cpm                 NUMERIC(10,2),
    fact_views               INTEGER,
    fact_ctr                 NUMERIC(5,2),
    fact_clicks              INTEGER,
    fact_cpc                 NUMERIC(10,2),
    fact_cpm                 NUMERIC(10,2),
    fact_carts               INTEGER,
    fact_orders              INTEGER,
    fact_revenue             NUMERIC(14,2),
    cr_to_cart               NUMERIC(5,2),
    cr_to_order              NUMERIC(5,2),
    -- Compliance checklists (cols 46-53 in Sheets).
    -- W1 (codex-arch-review): nullable. NULL = "not yet evaluated", false = "checked, failed",
    -- true = "checked, passed". Empty Sheets cells migrate as NULL, not as compliance failure.
    has_marking              BOOLEAN,
    has_contract             BOOLEAN,
    has_deeplink             BOOLEAN,
    has_closing_docs         BOOLEAN,
    has_full_recording       BOOLEAN,
    all_data_filled          BOOLEAN,
    has_quality_content      BOOLEAN,
    complies_with_rules      BOOLEAN,
    notes                    TEXT,
    archived_at              TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    sheet_row_id             TEXT,
    CONSTRAINT chk_int_channel CHECK (channel IN ('instagram','youtube','tiktok','telegram','vk','rutube','other')),
    CONSTRAINT chk_int_ad_format CHECK (ad_format IN ('short_video','long_video','image_post','text_post','live_stream','story','integration','long_post')),
    CONSTRAINT chk_int_marketplace CHECK (marketplace IN ('wb','ozon','both')),
    CONSTRAINT chk_int_stage CHECK (stage IN ('lead','negotiation','agreed','brief','awaiting_content','content_received','published','published_pending_metrics','paid','done')),
    CONSTRAINT chk_int_outcome CHECK (outcome IS NULL OR outcome IN ('cancelled','refunded','no_show')),
    CONSTRAINT chk_int_payment CHECK (payment_method IS NULL OR payment_method IN ('sbp_card','samozanyaty','ip','barter','other')),
    CONSTRAINT chk_int_costs_nonneg CHECK (
        COALESCE(cost_placement, 0) >= 0 AND
        COALESCE(cost_delivery, 0)  >= 0 AND
        COALESCE(cost_goods, 0)     >= 0
    ),
    -- C1 (codex-arch-review): exempt list extended to include awaiting_content + content_received.
    -- Rationale: erid is obtained when the post goes live (published+); content prep stages must
    -- be allowed without erid. The CHECK still blocks promotion to 'published' without erid for
    -- posts dated after 2022-09-01 (Russian advertising law).
    CONSTRAINT chk_int_erid CHECK (
        erid IS NOT NULL OR
        publish_date < DATE '2022-09-01' OR
        stage IN ('lead','negotiation','agreed','brief','awaiting_content','content_received')
    ),
    CONSTRAINT chk_int_reschedule CHECK (reschedule_count >= 0),
    CONSTRAINT uq_integrations_sheet_row UNIQUE (sheet_row_id)
);

CREATE INDEX idx_integrations_blogger ON integrations (blogger_id) WHERE archived_at IS NULL;
CREATE INDEX idx_integrations_marketer ON integrations (marketer_id) WHERE archived_at IS NULL;
CREATE INDEX idx_integrations_publish_date ON integrations (publish_date DESC) WHERE archived_at IS NULL;
CREATE INDEX idx_integrations_stage ON integrations (stage) WHERE archived_at IS NULL AND outcome IS NULL;
CREATE INDEX idx_integrations_outcome ON integrations (outcome) WHERE outcome IS NOT NULL;
CREATE INDEX idx_integrations_marketplace ON integrations (marketplace);
CREATE UNIQUE INDEX uq_integrations_erid ON integrations (erid) WHERE erid IS NOT NULL AND archived_at IS NULL;


-- =============================================================================
-- 12. integration_substitute_articles (M:N junction; multi-model support)
-- =============================================================================
CREATE TABLE integration_substitute_articles (
    id                     BIGSERIAL PRIMARY KEY,
    integration_id         BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    substitute_article_id  BIGINT NOT NULL REFERENCES substitute_articles(id) ON DELETE RESTRICT,
    display_order          INTEGER NOT NULL DEFAULT 1,
    tracking_url           TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_isa_order CHECK (display_order >= 1),
    CONSTRAINT uq_isa UNIQUE (integration_id, substitute_article_id)
);

CREATE INDEX idx_isa_sub ON integration_substitute_articles (substitute_article_id);
CREATE INDEX idx_isa_int ON integration_substitute_articles (integration_id);


-- =============================================================================
-- 13. integration_promo_codes (M:N junction; mirrors substitute junction)
-- =============================================================================
CREATE TABLE integration_promo_codes (
    id              BIGSERIAL PRIMARY KEY,
    integration_id  BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    promo_code_id   BIGINT NOT NULL REFERENCES promo_codes(id) ON DELETE RESTRICT,
    display_order   INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ipc_order CHECK (display_order >= 1),
    CONSTRAINT uq_ipc UNIQUE (integration_id, promo_code_id)
);

CREATE INDEX idx_ipc_promo ON integration_promo_codes (promo_code_id);
CREATE INDEX idx_ipc_int ON integration_promo_codes (integration_id);


-- =============================================================================
-- 14. integration_posts (1:N posts under one integration)
-- =============================================================================
CREATE TABLE integration_posts (
    id              BIGSERIAL PRIMARY KEY,
    integration_id  BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,
    ad_format       TEXT NOT NULL,
    post_url        TEXT,
    screen_url      TEXT,
    erid            TEXT,
    posted_at       TIMESTAMPTZ,
    fact_views      INTEGER,
    fact_clicks     INTEGER,
    fact_ctr        NUMERIC(5,2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ip_channel CHECK (channel IN ('instagram','youtube','tiktok','telegram','vk','rutube','other')),
    CONSTRAINT chk_ip_ad_format CHECK (ad_format IN ('short_video','long_video','image_post','text_post','live_stream','story','integration','long_post')),
    CONSTRAINT chk_ip_metrics CHECK (
        COALESCE(fact_views, 0)  >= 0 AND
        COALESCE(fact_clicks, 0) >= 0
    )
);

CREATE INDEX idx_ip_int ON integration_posts (integration_id);
CREATE INDEX idx_ip_posted ON integration_posts (posted_at DESC) WHERE posted_at IS NOT NULL;


-- =============================================================================
-- 15. integration_metrics_snapshots (capture fact metric curves over time)
-- =============================================================================
CREATE TABLE integration_metrics_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    integration_id  BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    fact_views      INTEGER,
    fact_clicks     INTEGER,
    fact_ctr        NUMERIC(5,2),
    fact_cpm        NUMERIC(10,2),
    fact_carts      INTEGER,
    fact_orders     INTEGER,
    fact_revenue    NUMERIC(14,2),
    source          TEXT NOT NULL DEFAULT 'manual',
    CONSTRAINT chk_ims_source CHECK (source IN ('manual','api','import','sheets'))
);

CREATE INDEX idx_ims_int_captured ON integration_metrics_snapshots (integration_id, captured_at DESC);


-- =============================================================================
-- 16. integration_stage_history (Trello dwell-time analytics)
-- =============================================================================
CREATE TABLE integration_stage_history (
    id              BIGSERIAL PRIMARY KEY,
    integration_id  BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    from_stage      TEXT,
    to_stage        TEXT NOT NULL,
    entered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    by_marketer_id  BIGINT REFERENCES marketers(id) ON DELETE SET NULL,
    comment         TEXT
);

CREATE INDEX idx_ish_int ON integration_stage_history (integration_id, entered_at DESC);

-- Trigger: capture stage transitions
CREATE OR REPLACE FUNCTION trg_integration_stage_history() RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path = crm, public
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO crm.integration_stage_history (integration_id, from_stage, to_stage, entered_at)
        VALUES (NEW.id, NULL, NEW.stage, COALESCE(NEW.created_at, now()));
    ELSIF TG_OP = 'UPDATE' AND OLD.stage IS DISTINCT FROM NEW.stage THEN
        INSERT INTO crm.integration_stage_history (integration_id, from_stage, to_stage, entered_at)
        VALUES (NEW.id, OLD.stage, NEW.stage, now());
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER integrations_stage_history_trg
    AFTER INSERT OR UPDATE OF stage ON integrations
    FOR EACH ROW EXECUTE FUNCTION trg_integration_stage_history();


-- =============================================================================
-- 17. integration_tags (M:N junction)
-- =============================================================================
CREATE TABLE integration_tags (
    integration_id  BIGINT NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    tag_id          BIGINT NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (integration_id, tag_id)
);

CREATE INDEX idx_int_tags_tag ON integration_tags (tag_id);


-- =============================================================================
-- 18. blogger_candidates (shortlist; "inst на проверку")
-- =============================================================================
CREATE TABLE blogger_candidates (
    id                    BIGSERIAL PRIMARY KEY,
    handle                TEXT NOT NULL,
    source_url            TEXT,
    contact               TEXT,
    audience              INTEGER,
    avg_cpm_estimate      NUMERIC(10,2),
    why_interesting       TEXT,
    status                TEXT NOT NULL DEFAULT 'new',
    converted_blogger_id  BIGINT REFERENCES bloggers(id) ON DELETE SET NULL,
    notes                 TEXT,
    found_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    sheet_row_id          TEXT,
    CONSTRAINT chk_bc_status CHECK (status IN ('new','contacted','approved','rejected','converted')),
    CONSTRAINT uq_bc_sheet_row UNIQUE (sheet_row_id)
);

CREATE INDEX idx_bc_status ON blogger_candidates (status) WHERE status NOT IN ('rejected','converted');


-- =============================================================================
-- 19. branded_queries
-- =============================================================================
CREATE TABLE branded_queries (
    id               BIGSERIAL PRIMARY KEY,
    query            TEXT NOT NULL,
    canonical_brand  TEXT NOT NULL DEFAULT 'Wookiee',
    model_osnova_id  INTEGER REFERENCES modeli_osnova(id) ON DELETE SET NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- LOWER is IMMUTABLE; unaccent dropped (was STABLE, not allowed in STORED).
    -- For Wookiee branded search queries (RU + WB) unaccent adds little value.
    query_normalized TEXT GENERATED ALWAYS AS (LOWER(query)) STORED,
    CONSTRAINT chk_bq_status CHECK (status IN ('active','paused','archived'))
);

CREATE UNIQUE INDEX uq_bq_normalized ON branded_queries (query_normalized);
CREATE INDEX idx_bq_trgm ON branded_queries USING gin (query_normalized gin_trgm_ops);
CREATE INDEX idx_bq_model_osnova ON branded_queries (model_osnova_id) WHERE model_osnova_id IS NOT NULL;


-- =============================================================================
-- 20. audit_log (single journal; FOR EACH STATEMENT trigger)
-- =============================================================================
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    record_id   BIGINT,
    action      TEXT NOT NULL,
    old_data    JSONB,
    new_data    JSONB,
    by_marketer_id BIGINT REFERENCES marketers(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_audit_action CHECK (action IN ('insert','update','delete'))
);

CREATE INDEX idx_audit_record ON audit_log (table_name, record_id, created_at DESC);
CREATE INDEX idx_audit_created ON audit_log (created_at DESC);


-- =============================================================================
-- 21. sheets_sync_state
-- =============================================================================
CREATE TABLE sheets_sync_state (
    id                    BIGSERIAL PRIMARY KEY,
    target_table          TEXT NOT NULL,
    sheet_id              TEXT NOT NULL,
    sheet_range           TEXT,
    last_pulled_at        TIMESTAMPTZ,
    last_pushed_at        TIMESTAMPTZ,
    last_etag             TEXT,
    row_count_processed   INTEGER,
    errors                JSONB,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sss UNIQUE (target_table, sheet_id, sheet_range)
);


-- =============================================================================
-- updated_at triggers (DRY helper)
-- =============================================================================
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'marketers','bloggers','content_brief_templates','briefs',
        'substitute_articles','promo_codes','integrations','sheets_sync_state'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at()',
            t, t
        );
    END LOOP;
END$$;


-- =============================================================================
-- C4 (codex-arch-review): audit_log trigger function + attachment to core tables.
-- FOR EACH STATEMENT with transition tables = one INSERT per statement, not per row.
-- During bulk import: SET LOCAL session_replication_role = replica; -- bypasses triggers.
-- =============================================================================
CREATE OR REPLACE FUNCTION trg_audit_log() RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path = crm, public
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO crm.audit_log (table_name, record_id, action, new_data)
        SELECT TG_TABLE_NAME, n.id, 'insert', to_jsonb(n) FROM new_table n;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO crm.audit_log (table_name, record_id, action, old_data, new_data)
        SELECT TG_TABLE_NAME, n.id, 'update', to_jsonb(o), to_jsonb(n)
        FROM old_table o JOIN new_table n USING (id);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO crm.audit_log (table_name, record_id, action, old_data)
        SELECT TG_TABLE_NAME, o.id, 'delete', to_jsonb(o) FROM old_table o;
    END IF;
    RETURN NULL;
END;
$$;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['integrations','substitute_articles','promo_codes','bloggers'] LOOP
        EXECUTE format($f$
            CREATE TRIGGER %I_audit_ins
            AFTER INSERT ON %I
            REFERENCING NEW TABLE AS new_table
            FOR EACH STATEMENT EXECUTE FUNCTION trg_audit_log()
        $f$, t, t);
        EXECUTE format($f$
            CREATE TRIGGER %I_audit_upd
            AFTER UPDATE ON %I
            REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table
            FOR EACH STATEMENT EXECUTE FUNCTION trg_audit_log()
        $f$, t, t);
        EXECUTE format($f$
            CREATE TRIGGER %I_audit_del
            AFTER DELETE ON %I
            REFERENCING OLD TABLE AS old_table
            FOR EACH STATEMENT EXECUTE FUNCTION trg_audit_log()
        $f$, t, t);
    END LOOP;
END$$;


-- =============================================================================
-- W7 (codex-arch-review): v_blogger_totals materialized view (landing screen agg).
-- Refresh strategy: pg_cron every 5 min, CONCURRENTLY (requires unique index below).
-- Weighted-average CPM per Wookiee analytics rule (sum(cost) / sum(views) * 1000).
-- NOTE: RLS does not apply to materialized views. Rely on view definition for filtering.
-- =============================================================================
CREATE MATERIALIZED VIEW v_blogger_totals AS
SELECT
    b.id                                                AS blogger_id,
    b.display_handle,
    b.default_marketer_id,
    COUNT(DISTINCT i.id)                                AS integrations_count,
    COUNT(*) FILTER (
        WHERE i.stage IN ('published','paid','done')
          AND (i.outcome IS NULL OR i.outcome NOT IN ('cancelled','no_show'))
    )                                                   AS integrations_done,
    MAX(i.publish_date)                                 AS last_integration_at,
    COALESCE(SUM(i.total_cost), 0)                      AS total_spent,
    -- Weighted average CPM: sum(cost) / sum(views) * 1000
    CASE WHEN COALESCE(SUM(i.fact_views), 0) > 0
         THEN SUM(i.total_cost) * 1000.0 / SUM(i.fact_views)
         ELSE NULL END                                  AS avg_cpm_fact,
    COALESCE(SUM(i.fact_orders), 0)                     AS total_orders_fact,
    COALESCE(SUM(i.fact_revenue), 0)                    AS total_revenue_fact
FROM bloggers b
LEFT JOIN integrations i ON i.blogger_id = b.id
    AND i.archived_at IS NULL
    AND (i.outcome IS NULL OR i.outcome NOT IN ('cancelled','no_show'))
WHERE b.archived_at IS NULL
GROUP BY b.id, b.display_handle, b.default_marketer_id;

CREATE UNIQUE INDEX uq_v_blogger_totals ON v_blogger_totals (blogger_id);

-- Initial refresh (won't have data on fresh schema, but ensures index works)
REFRESH MATERIALIZED VIEW v_blogger_totals;


-- =============================================================================
-- W10 (codex-arch-review): retention policy stubs for time-series tables.
-- Schedule via pg_cron after data starts accumulating. Defaults: 2 years.
-- =============================================================================
-- Example schedules (uncomment after enabling pg_cron):
-- SELECT cron.schedule(
--     'samw-retention',
--     '0 3 * * 0',  -- Sundays 03:00
--     $$DELETE FROM substitute_article_metrics_weekly
--       WHERE week_start < (now() - INTERVAL '2 years')::date$$
-- );
-- SELECT cron.schedule(
--     'ims-retention',
--     '0 3 * * 0',
--     $$DELETE FROM integration_metrics_snapshots
--       WHERE captured_at < now() - INTERVAL '2 years'$$
-- );
-- SELECT cron.schedule(
--     'audit-retention',
--     '0 3 1 * *',  -- monthly on 1st
--     $$DELETE FROM audit_log WHERE created_at < now() - INTERVAL '2 years'$$
-- );


-- =============================================================================
-- RLS: enable + policies (DEC-7: service_role only on local; authenticated read-only)
--
-- W8 (codex-arch-review) IMPORTANT NOTE:
-- The Supabase service_role / postgres role BYPASSES RLS entirely. The policies
-- below are defense-in-depth for future authenticated access, not active filters
-- for the current local Python BFF setup. The 'authenticated_select_*' policies
-- use USING(true) — full read access for any authenticated user. When real
-- per-user auth is added, replace USING(true) with ownership predicates
-- (e.g., USING(marketer_id IN (SELECT id FROM marketers WHERE auth_user_id = auth.uid()))).
-- =============================================================================
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'marketers','tags','bloggers','blogger_channels','blogger_tags',
        'content_brief_templates','briefs','brief_versions',
        'substitute_articles','substitute_article_metrics_weekly',
        'promo_codes','integrations',
        'integration_substitute_articles','integration_promo_codes',
        'integration_posts','integration_metrics_snapshots','integration_stage_history',
        'integration_tags','blogger_candidates','branded_queries',
        'audit_log','sheets_sync_state'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY service_role_full_%I ON %I FOR ALL TO postgres USING (true) WITH CHECK (true)',
            t, t
        );
        EXECUTE format(
            'CREATE POLICY authenticated_select_%I ON %I FOR SELECT TO authenticated USING (true)',
            t, t
        );
        EXECUTE format('REVOKE ALL ON %I FROM anon', t);
    END LOOP;
END$$;


-- =============================================================================
-- Sanity check (post-migration assertions)
-- =============================================================================
DO $$
DECLARE expected_tables INT := 22; actual_tables INT;
BEGIN
    SELECT COUNT(*) INTO actual_tables
    FROM information_schema.tables
    WHERE table_schema = 'crm'
      AND table_name IN (
        'marketers','tags','bloggers','blogger_channels','blogger_tags',
        'content_brief_templates','briefs','brief_versions',
        'substitute_articles','substitute_article_metrics_weekly',
        'promo_codes','integrations',
        'integration_substitute_articles','integration_promo_codes',
        'integration_posts','integration_metrics_snapshots','integration_stage_history',
        'integration_tags','blogger_candidates','branded_queries',
        'audit_log','sheets_sync_state'
      );
    IF actual_tables <> expected_tables THEN
        RAISE EXCEPTION 'Migration 008 incomplete: expected % tables, got %', expected_tables, actual_tables;
    END IF;
END$$;

COMMIT;
