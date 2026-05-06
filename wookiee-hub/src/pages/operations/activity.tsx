import { useState, useEffect, useMemo } from 'react'
import { CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { fetchRuns, getAgentLabel, AGENT_TO_LABEL } from '@/lib/activity-service'
import { cn } from '@/lib/utils'
import type { AgentRun, RunStatus, RunsFilter } from '@/types/activity'

// ─── helpers ────────────────────────────────────────────────────────────────

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${dd}.${mm}.${yyyy} ${hh}:${min}`
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms >= 1000) return `${Math.round(ms / 1000)}с`
  return `${ms}мс`
}

function formatCost(usd: number): string {
  if (!usd) return '—'
  return `$${usd.toFixed(4)}`
}

function formatNumber(n: number): string {
  return n.toLocaleString('ru-RU')
}

// Build reverse map: label → agentNames[]
function buildLabelToAgents(): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const [agent, label] of Object.entries(AGENT_TO_LABEL)) {
    const existing = map.get(label) ?? []
    existing.push(agent)
    map.set(label, existing)
  }
  return map
}

const LABEL_TO_AGENTS = buildLabelToAgents()
// Unique sorted labels for the filter
const UNIQUE_LABELS: string[] = Array.from(LABEL_TO_AGENTS.keys()).sort((a, b) => a.localeCompare(b, 'ru'))

const STATUS_OPTIONS: { value: RunStatus | ''; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'success', label: 'Успех' },
  { value: 'error', label: 'Ошибка' },
  { value: 'timeout', label: 'Таймаут' },
]

const STATUS_LABELS: Record<RunStatus, string> = {
  success: 'Успех',
  error: 'Ошибка',
  timeout: 'Таймаут',
}

// ─── status icon ────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: RunStatus }) {
  if (status === 'success') {
    return <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
  }
  if (status === 'error') {
    return <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
  }
  return <Clock className="w-4 h-4 text-amber-600 flex-shrink-0" />
}

// ─── run row ────────────────────────────────────────────────────────────────

function RunRow({
  run,
  expanded,
  onToggle,
}: {
  run: AgentRun
  expanded: boolean
  onToggle: () => void
}) {
  const statusColorClass =
    run.status === 'success'
      ? 'bg-green-50 border-green-200 text-green-600'
      : run.status === 'error'
        ? 'bg-red-50 border-red-200 text-red-600'
        : 'bg-amber-50 border-amber-200 text-amber-600'

  return (
    <>
      {/* Main row */}
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3 border-b border-border hover:bg-muted/40 transition-colors cursor-pointer select-none',
          expanded && 'bg-muted/30',
        )}
        onClick={onToggle}
      >
        {/* Status icon */}
        <StatusIcon status={run.status} />

        {/* Agent label + name */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-foreground truncate">
            {getAgentLabel(run.agentName)}
          </p>
          <p className="text-[11px] text-muted-foreground font-mono truncate">{run.agentName}</p>
        </div>

        {/* Status badge */}
        <span
          className={cn(
            'hidden sm:inline-flex text-[10px] font-semibold border rounded px-1.5 py-0.5 uppercase tracking-wider',
            statusColorClass,
          )}
        >
          {STATUS_LABELS[run.status]}
        </span>

        {/* Time */}
        <p className="text-[12px] text-muted-foreground whitespace-nowrap hidden md:block">
          {formatDateTime(run.startedAt)}
        </p>

        {/* Duration */}
        <p className="text-[12px] text-muted-foreground w-14 text-right">
          {formatDuration(run.durationMs)}
        </p>

        {/* Cost */}
        <p className="text-[12px] text-muted-foreground w-20 text-right">
          {formatCost(run.costUsd)}
        </p>

        {/* Expand chevron */}
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        )}
      </div>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="px-4 py-3 bg-muted/20 border-b border-border space-y-2 text-[12px]">
          {/* Error */}
          {run.errorMessage && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 font-mono text-[11px] whitespace-pre-wrap break-all">
              {run.errorMessage}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1.5 text-muted-foreground">
            {/* Model */}
            {run.model && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Модель</span>
                <span className="text-foreground font-mono">{run.model}</span>
              </div>
            )}

            {/* Tokens */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Токены</span>
              <span className="text-foreground">
                {formatNumber(run.promptTokens)} + {formatNumber(run.completionTokens)} ={' '}
                {formatNumber(run.totalTokens)}
              </span>
            </div>

            {/* Cost full */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Стоимость</span>
              <span className="text-foreground">${run.costUsd.toFixed(6)}</span>
            </div>

            {/* Trigger */}
            {run.trigger && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Триггер</span>
                <span className="text-foreground">{run.trigger}</span>
              </div>
            )}

            {/* Task type */}
            {run.taskType && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Тип задачи</span>
                <span className="text-foreground">{run.taskType}</span>
              </div>
            )}

            {/* Started at full */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Запуск</span>
              <span className="text-foreground">{formatDateTime(run.startedAt)}</span>
            </div>
          </div>

          {/* Parent run ID */}
          {run.parentRunId && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Parent Run ID:{' '}
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">{run.parentRunId}</span>
            </div>
          )}

          {/* Run ID */}
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Run ID:{' '}
            </span>
            <span className="font-mono text-[11px] text-muted-foreground">{run.runId}</span>
          </div>
        </div>
      )}
    </>
  )
}

// ─── main page ──────────────────────────────────────────────────────────────

export function ActivityPage() {
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [toolLabel, setToolLabel] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<RunStatus | ''>('')
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [limit, setLimit] = useState(50)
  const [hasMore, setHasMore] = useState(false)

  // Build filter from current state
  const filter = useMemo<RunsFilter>(() => {
    const f: RunsFilter = {}
    if (toolLabel) {
      f.agentNames = LABEL_TO_AGENTS.get(toolLabel) ?? []
    }
    if (statusFilter) {
      f.status = statusFilter as RunStatus
    }
    if (dateFrom) {
      f.dateFrom = dateFrom
    }
    if (dateTo) {
      // Include full end day: append end-of-day time
      f.dateTo = `${dateTo}T23:59:59`
    }
    return f
  }, [toolLabel, statusFilter, dateFrom, dateTo])

  // Fetch whenever filter or limit changes
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchRuns(filter, limit).then((data) => {
      if (!cancelled) {
        setRuns(data)
        setHasMore(data.length === limit)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [filter, limit])

  // When filters change (not limit), reset limit
  useEffect(() => {
    setLimit(50)
    setExpandedId(null)
  }, [toolLabel, statusFilter, dateFrom, dateTo])

  // KPI counts
  const totalShown = runs.length
  const successCount = runs.filter((r) => r.status === 'success').length
  const failCount = runs.filter((r) => r.status === 'error' || r.status === 'timeout').length

  function handleToggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  function handleLoadMore() {
    setLimit((prev) => prev + 50)
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">История запусков</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Все запуски агентов и скиллов системы Wookiee
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            label: 'Всего запусков',
            value: totalShown,
            sub: 'в выборке',
            cls: 'text-foreground',
          },
          {
            label: 'Успешных',
            value: successCount,
            sub: `из ${totalShown}`,
            cls: totalShown > 0 ? 'text-green-600' : 'text-foreground',
          },
          {
            label: 'С ошибкой',
            value: failCount,
            sub: 'ошибки + таймауты',
            cls: failCount > 0 ? 'text-red-600' : 'text-foreground',
          },
        ].map(({ label, value, sub, cls }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">
              {label}
            </p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-card border border-border rounded-xl p-4 flex flex-wrap gap-4 items-end">
        {/* Tool filter */}
        <div className="flex flex-col gap-1 min-w-[180px]">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Инструмент
          </label>
          <select
            value={toolLabel}
            onChange={(e) => setToolLabel(e.target.value)}
            className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">Все</option>
            {UNIQUE_LABELS.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Status filter */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Статус
          </label>
          <div className="flex gap-1">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value)}
                className={cn(
                  'text-[12px] px-2.5 py-1.5 rounded-lg border transition-colors',
                  statusFilter === opt.value
                    ? 'bg-foreground text-background border-foreground'
                    : 'bg-background border-border text-muted-foreground hover:bg-muted/40',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Date from */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            От
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* Date to */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            До
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* Reset button */}
        {(toolLabel || statusFilter || dateFrom || dateTo) && (
          <button
            onClick={() => {
              setToolLabel('')
              setStatusFilter('')
              setDateFrom('')
              setDateTo('')
            }}
            className="text-[12px] text-muted-foreground hover:text-foreground transition-colors py-1.5 self-end"
          >
            Сбросить
          </button>
        )}
      </div>

      {/* Column header row */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-muted/30">
          <div className="w-4" />
          <p className="flex-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Агент
          </p>
          <p className="hidden sm:block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-16">
            Статус
          </p>
          <p className="hidden md:block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-32">
            Время
          </p>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-14 text-right">
            Длит.
          </p>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-20 text-right">
            Стоимость
          </p>
          <div className="w-4" />
        </div>

        {/* Loading state */}
        {loading && (
          <p className="text-sm text-muted-foreground py-8 text-center">Загружаю запуски...</p>
        )}

        {/* Empty state */}
        {!loading && runs.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-sm text-muted-foreground">Запуски не найдены</p>
            <p className="text-[12px] text-muted-foreground mt-1">Попробуйте изменить фильтры</p>
          </div>
        )}

        {/* Runs */}
        {!loading &&
          runs.map((run) => (
            <RunRow
              key={run.id}
              run={run}
              expanded={expandedId === run.id}
              onToggle={() => handleToggleExpand(run.id)}
            />
          ))}
      </div>

      {/* Load more */}
      {!loading && hasMore && (
        <div className="flex justify-center">
          <button
            onClick={handleLoadMore}
            className="text-[13px] text-muted-foreground border border-border bg-card hover:bg-muted/40 transition-colors rounded-lg px-5 py-2"
          >
            Загрузить ещё
          </button>
        </div>
      )}
    </div>
  )
}
