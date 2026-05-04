-- 013_audience_fields_russian_stages.sql
-- 1. Add 5 audience columns that were missing from original schema.
-- 2. Migrate stage column from English values to Russian (8-stage funnel agreed 2026-04-30).

-- ── Audience columns ──────────────────────────────────────────────────────────
ALTER TABLE crm.integrations
    ADD COLUMN IF NOT EXISTS theme            TEXT,
    ADD COLUMN IF NOT EXISTS audience_age     TEXT,
    ADD COLUMN IF NOT EXISTS subscribers      INTEGER,
    ADD COLUMN IF NOT EXISTS min_reach        INTEGER,
    ADD COLUMN IF NOT EXISTS engagement_rate  NUMERIC(5,2);

-- ── Stage migration ───────────────────────────────────────────────────────────
-- Drop the old English CHECK so UPDATE can run first (avoids constraint violation).
ALTER TABLE crm.integrations DROP CONSTRAINT IF EXISTS chk_int_stage;
-- Also drop the erid constraint that references stage names (will re-add below).
ALTER TABLE crm.integrations DROP CONSTRAINT IF EXISTS chk_int_erid;

-- Historical rows (before May 2026) → завершено; future rows → запланировано.
-- Manual stage transitions in the Kanban UI are the source of truth going forward.
UPDATE crm.integrations
SET stage = CASE
    WHEN publish_date < '2026-05-01' THEN 'завершено'
    ELSE 'запланировано'
END;

-- Change default for new rows.
ALTER TABLE crm.integrations ALTER COLUMN stage SET DEFAULT 'переговоры';

-- Re-add stage CHECK with Russian values.
ALTER TABLE crm.integrations
    ADD CONSTRAINT chk_int_stage CHECK (stage IN (
        'переговоры',
        'согласовано',
        'отправка_комплекта',
        'контент',
        'запланировано',
        'аналитика',
        'завершено',
        'архив'
    ));

-- Re-add erid CHECK (Russian stage names, same enforcement rule as before:
-- erid required once a post is published/beyond-content stage).
ALTER TABLE crm.integrations
    ADD CONSTRAINT chk_int_erid CHECK (
        erid IS NOT NULL
        OR stage IN ('переговоры', 'согласовано', 'отправка_комплекта', 'контент', 'архив')
        OR publish_date < '2022-09-01'
    );
