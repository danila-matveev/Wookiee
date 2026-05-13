import { supabase } from '@/lib/supabase'

export interface SyncLogEntry {
  id: number
  job_name: string
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  rows_processed: number | null
  rows_written: number | null
  weeks_covered: string | null
  error_message: string | null
  triggered_by: string | null
}

export async function fetchLastSync(jobName: string): Promise<SyncLogEntry | null> {
  const { data, error } = await supabase
    .schema('marketing').from('sync_log')
    .select('*')
    .eq('job_name', jobName)
    .order('finished_at', { ascending: false, nullsFirst: false })
    .limit(1)
    .maybeSingle()
  if (error) throw error
  return (data as SyncLogEntry | null)
}

// ---------------------------------------------------------------------------
// analytics_api: trigger sync + poll status (Task B.2.2)
// ---------------------------------------------------------------------------

const ANALYTICS_API_URL = import.meta.env.VITE_ANALYTICS_API_URL ?? ''
const ANALYTICS_API_KEY = import.meta.env.VITE_ANALYTICS_API_KEY ?? ''

/**
 * Job names exposed by `services/analytics_api/marketing.py`.
 * Hyphenated form ("search-queries", "promocodes") = URL slug; the backend
 * maps these to internal sync_log job_name values written by the cron scripts.
 */
export type SyncJobName = 'search-queries' | 'promocodes'

export interface TriggerSyncResponse {
  job_name: string
  status: 'running'
  sync_log_id: number
  started_at: string
}

export interface SyncStatusResponse {
  status: 'never_run' | 'running' | 'success' | 'failed'
  job_name?: string
  id?: number
  started_at?: string | null
  finished_at?: string | null
  rows_processed?: number | null
  error_message?: string | null
}

function _syncUrl(path: string): string {
  // Use full ANALYTICS_API_URL when configured (cross-origin), else relative
  // (lets vite dev proxy / same-origin deployments work without env vars).
  const base = ANALYTICS_API_URL || window.location.origin
  return new URL(path, base).toString()
}

export async function triggerSync(job: SyncJobName): Promise<TriggerSyncResponse> {
  const r = await fetch(_syncUrl(`/api/marketing/sync/${job}`), {
    method: 'POST',
    headers: { 'X-API-Key': ANALYTICS_API_KEY },
  })
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`Sync trigger failed (${r.status}): ${text}`)
  }
  return r.json()
}

export async function fetchSyncStatus(job: SyncJobName): Promise<SyncStatusResponse> {
  const r = await fetch(_syncUrl(`/api/marketing/sync/${job}/status`), {
    headers: { 'X-API-Key': ANALYTICS_API_KEY },
  })
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`Sync status failed (${r.status}): ${text}`)
  }
  return r.json()
}
