-- Migration 031: fix_log table for Nighttime DevOps Agent
--
-- Wave B5 of Nighttime DevOps Agent (Wave E2 will write to this table,
-- rollback-test.yml will read from it).
--
-- Plan: docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md §4.1
-- Renumbered from 030 → 031 because PR #137 (catalog_export_views) merged
-- to main and claimed 030 first. Same DDL, table already applied as 031
-- to production Supabase 2026-05-14.
--
-- Purpose: every fix the night agent applies is logged here with the exact
-- rollback command. The weekly rollback-test.yml workflow verifies that those
-- commands actually work. Without this table the agent has no audit trail
-- and no reversibility guarantee.
--
-- RLS: service_role only (matches CLAUDE.md project rule for new Supabase tables).
-- anon/authenticated have no access.

CREATE TABLE IF NOT EXISTS public.fix_log (
  id                BIGSERIAL PRIMARY KEY,
  occurred_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  run_date          DATE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')::DATE,
  run_id            TEXT NOT NULL,                    -- "night-coordinator-2026-05-14-0400-utc"
  agent             TEXT NOT NULL,                    -- "hygiene-autofix" | "code-quality-scan" | "night-coordinator"
  finding_id        TEXT NOT NULL,                    -- matches finding.id in JSON reports
  finding_type      TEXT NOT NULL,                    -- alias of category for downstream compat
  category          TEXT NOT NULL,                    -- orphan-imports | lint-error | dead-code | ...
  severity          TEXT NOT NULL,                    -- low | medium | high | critical
  fix_action        TEXT NOT NULL,                    -- "deleted" | "edited" | "moved" | "ruff-fix" | ...
  files_changed     JSONB NOT NULL,                   -- ["shared/helpers_old.py", ...]
  commit_sha        TEXT NOT NULL,                    -- SHA of the commit that applied the fix
  rollback_commit   TEXT,                             -- parent commit SHA before the fix (for `git revert`)
  pr_number         INTEGER,                          -- linked PR
  rollback_command  TEXT NOT NULL,                    -- "git revert <sha>" — must parse cleanly
  rollback_verified BOOLEAN NOT NULL DEFAULT FALSE,   -- weekly rollback-test sets this true
  rolled_back_at    TIMESTAMPTZ,                      -- non-null = actually rolled back
  rolled_back_reason TEXT,
  metadata          JSONB                             -- codex_confidence, token_usage, etc.
);

CREATE INDEX IF NOT EXISTS idx_fix_log_run_date ON public.fix_log (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_fix_log_agent_date ON public.fix_log (agent, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_fix_log_run_id ON public.fix_log (run_id);
CREATE INDEX IF NOT EXISTS idx_fix_log_finding_id ON public.fix_log (finding_id);
CREATE INDEX IF NOT EXISTS idx_fix_log_occurred_at ON public.fix_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_fix_log_rolled_back
  ON public.fix_log (rolled_back_at)
  WHERE rolled_back_at IS NOT NULL;

-- RLS — anon/authenticated blocked, only service_role writes/reads.
ALTER TABLE public.fix_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS fix_log_service_role_all ON public.fix_log;
CREATE POLICY fix_log_service_role_all ON public.fix_log
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

REVOKE ALL ON public.fix_log FROM anon, authenticated;
GRANT ALL ON public.fix_log TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.fix_log_id_seq TO service_role;

COMMENT ON TABLE public.fix_log IS
  'Night DevOps agent audit trail. Every autofix is logged with rollback_command. '
  'Weekly rollback-test.yml verifies reversibility. RLS service_role-only.';
