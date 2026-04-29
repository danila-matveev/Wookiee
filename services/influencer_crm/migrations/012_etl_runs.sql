-- 012_etl_runs.sql
-- CRM-owned ETL telemetry table. Replaces tool_telemetry.agent_runs which is
-- a no-op since 2026-04-13 (audit remediation deprecated writes).
-- /ops/health reads from this table.

CREATE TABLE IF NOT EXISTS crm.etl_runs (
    id            BIGSERIAL PRIMARY KEY,
    agent         TEXT        NOT NULL,
    version       TEXT        NOT NULL DEFAULT '1.0.0',
    mode          TEXT        NOT NULL CHECK (mode IN ('full', 'incremental')),
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ,
    duration_ms   INTEGER,
    status        TEXT        NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    error_message TEXT,
    rows_loaded   JSONB
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_agent_started
    ON crm.etl_runs (agent, started_at DESC);

-- Retention: schedule weekly cleanup (>180 days) alongside the others from migration 011.
SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname = 'crm_etl_runs_retention';

SELECT cron.schedule(
    'crm_etl_runs_retention',
    '30 3 * * 0',
    $$DELETE FROM crm.etl_runs WHERE started_at < now() - INTERVAL '180 days'$$
);
