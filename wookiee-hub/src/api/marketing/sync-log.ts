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
