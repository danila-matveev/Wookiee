import { api } from '@/lib/api';

// Mirrors services/influencer_crm/schemas/ops.py (OpsHealth).
// Optional fields use `| null` to match Pydantic's `T | None = None`.
export interface EtlLastRun {
  started_at: string | null;
  status: string | null;
  duration_ms: number | null;
  error_message: string | null;
}

export interface EtlCounts {
  success: number;
  failed: number;
  running: number;
  stale_running: number;
}

export interface CronJobInfo {
  jobname: string;
  schedule: string;
  active: boolean;
}

export interface RetentionCounts {
  audit_log_eligible_for_delete: number;
  snapshots_eligible_for_delete: number;
}

export interface OpsHealth {
  etl_last_run: EtlLastRun;
  etl_last_24h: EtlCounts;
  mv_age_seconds: number | null;
  retention: RetentionCounts;
  cron_jobs: CronJobInfo[];
}

export function getOpsHealth(): Promise<OpsHealth> {
  return api.get<OpsHealth>('/ops/health');
}
