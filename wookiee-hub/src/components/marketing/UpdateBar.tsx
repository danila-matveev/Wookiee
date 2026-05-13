import { CheckCircle, AlertCircle, RefreshCw } from "lucide-react"
import {
  useLastSync,
  useSyncStatus,
  useTriggerSync,
} from "@/hooks/marketing/use-sync-log"
import type { SyncJobName } from "@/api/marketing/sync-log"
import { formatDateTime } from "@/lib/format"

export interface UpdateBarProps {
  /** API job slug (also used to derive the supabase sync_log job_name). */
  job: SyncJobName
}

// analytics_api uses hyphenated job slugs; supabase sync_log table stores
// the snake_case names written by the cron scripts.
const SUPABASE_JOB_NAME: Record<SyncJobName, string> = {
  'search-queries': 'search_queries_sync',
  'promocodes':     'promo_codes_sync',
}

export function UpdateBar({ job }: UpdateBarProps) {
  const lastSyncQ   = useLastSync(SUPABASE_JOB_NAME[job])
  const statusQ     = useSyncStatus(job)
  const triggerMut  = useTriggerSync()

  const live        = statusQ.data
  const lastSync    = lastSyncQ.data

  const isRunning   = live?.status === 'running' || triggerMut.isPending
  const isFailed    = !isRunning && live?.status === 'failed'
  const isSuccess   = !isRunning && (live?.status === 'success' || lastSync?.status === 'success')

  const finishedAt  = live?.finished_at ?? lastSync?.finished_at ?? null
  const lastUpdate  = finishedAt ? formatDateTime(finishedAt) : '—'
  const weeksCovered = lastSync?.weeks_covered ?? null
  const errMessage  = isFailed ? (live?.error_message ?? lastSync?.error_message ?? null) : null
  const rowsLive    = live?.rows_processed ?? null

  const Icon  = isFailed ? AlertCircle : CheckCircle
  const iconC = isFailed
    ? "text-[color:var(--wk-red,#b45309)]"
    : isSuccess
      ? "text-[color:var(--wk-green,#059669)]"
      : "text-muted-foreground"

  const onClick = () => {
    if (isRunning) return
    triggerMut.mutate(job)
  }

  return (
    <div className="flex items-center gap-3 px-6 py-1.5 bg-muted/30 border-b border-border text-[11px]">
      <Icon className={`w-3 h-3 ${iconC}`} aria-hidden />
      <span className="tabular-nums text-muted-foreground">{lastUpdate}</span>

      {isRunning && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span className="text-muted-foreground tabular-nums">
            {rowsLive != null
              ? `Обновление: ${rowsLive.toLocaleString('ru-RU')} строк`
              : 'Обновление…'}
          </span>
        </>
      )}

      {!isRunning && weeksCovered && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span className={iconC}>{weeksCovered}</span>
        </>
      )}

      {isFailed && errMessage && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span
            className="text-stone-700 truncate max-w-[320px]"
            title={errMessage}
          >
            {errMessage}
          </span>
        </>
      )}

      <button
        type="button"
        onClick={onClick}
        disabled={isRunning}
        className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium transition-colors border-border text-muted-foreground hover:bg-muted hover:border-foreground/30 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Обновить данные"
      >
        <RefreshCw className={`w-3 h-3 ${isRunning ? "animate-spin" : ""}`} aria-hidden />
        {isRunning ? "Обновляю…" : "Обновить"}
      </button>
    </div>
  )
}
