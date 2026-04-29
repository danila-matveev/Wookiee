-- 011_retention_jobs.sql
-- Weekly retention: delete stale audit + snapshot rows.
--
-- Schedules:
--   crm_audit_log_retention         — Sun 03:00 UTC, deletes crm.audit_log rows > 90 days
--   crm_metrics_snapshots_retention — Sun 03:15 UTC, deletes crm.integration_metrics_snapshots rows > 365 days
--
-- Column-name evidence:
--   crm.integration_metrics_snapshots.captured_at — confirmed by repo query in
--     shared/data_layer/influencer_crm/metrics.py:57 (SELECT ... captured_at ...).
--   crm.audit_log.created_at — assumed per plan default; no live DDL or repo query
--     references this column in the worktree. Verify column name on Supabase before applying:
--       SELECT column_name FROM information_schema.columns
--        WHERE table_schema = 'crm' AND table_name = 'audit_log';
--     Adapt the audit_log statement if the actual timestamp column differs.

SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname IN ('crm_audit_log_retention', 'crm_metrics_snapshots_retention');

SELECT cron.schedule(
    'crm_audit_log_retention',
    '0 3 * * 0',
    $$DELETE FROM crm.audit_log WHERE created_at < now() - INTERVAL '90 days'$$
);

SELECT cron.schedule(
    'crm_metrics_snapshots_retention',
    '15 3 * * 0',
    $$DELETE FROM crm.integration_metrics_snapshots WHERE captured_at < now() - INTERVAL '365 days'$$
);

-- Verification query (run manually):
--   SELECT jobname, schedule FROM cron.job WHERE jobname LIKE 'crm_%_retention';
-- Expected: 2 rows.
