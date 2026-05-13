import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchLastSync,
  fetchSyncStatus,
  triggerSync,
} from '@/api/marketing/sync-log'
import type { SyncJobName } from '@/api/marketing/sync-log'

export const syncLogKeys = {
  last:   (jobName: string)        => ['marketing', 'sync-log', jobName] as const,
  status: (job: SyncJobName)       => ['marketing', 'sync-status', job] as const,
}

export function useLastSync(jobName: string) {
  return useQuery({
    queryKey: syncLogKeys.last(jobName),
    queryFn: () => fetchLastSync(jobName),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    refetchOnWindowFocus: true,
  })
}

/**
 * Trigger a marketing sync via analytics_api.
 *
 * Invalidates the matching sync-status query on success so the polling query
 * picks up the new 'running' row immediately.
 */
export function useTriggerSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (job: SyncJobName) => triggerSync(job),
    onSuccess: (_data, job) => {
      qc.invalidateQueries({ queryKey: syncLogKeys.status(job) })
    },
  })
}

/**
 * Poll sync status from analytics_api.
 *
 * - Polls every 2s while status === 'running'; idles otherwise.
 * - When `enabled` is false (e.g. analytics_api not configured) the query is
 *   skipped entirely — UpdateBar then falls back to its supabase-driven
 *   `useLastSync` data only.
 */
export function useSyncStatus(job: SyncJobName, enabled: boolean = true) {
  return useQuery({
    queryKey: syncLogKeys.status(job),
    queryFn: () => fetchSyncStatus(job),
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2000 : false),
    refetchIntervalInBackground: false,
    staleTime: 0,
    enabled,
  })
}
