-- 010_pg_cron_mv_refresh.sql
-- Schedule v_blogger_totals refresh every 5 minutes via pg_cron.
-- Idempotent: drops the prior schedule if it exists, then inserts.

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Remove any previously-scheduled job with this name (re-run safety)
SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname = 'crm_v_blogger_totals_refresh';

SELECT cron.schedule(
    'crm_v_blogger_totals_refresh',
    '*/5 * * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY crm.v_blogger_totals$$
);

-- Verification query (run manually): SELECT * FROM cron.job WHERE jobname = 'crm_v_blogger_totals_refresh';
