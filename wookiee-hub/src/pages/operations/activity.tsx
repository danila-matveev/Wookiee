import { useState, useEffect, useMemo } from 'react'
import {
  CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp,
  ExternalLink, Bot, Wrench, Loader2
} from 'lucide-react'
import { fetchRuns, fetchToolRuns, getAgentLabel, AGENT_TO_LABEL } from '@/lib/activity-service'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/layout/page-header'
import { useDocumentTitle } from '@/hooks/use-document-title'
import type { AgentRun, ToolRun, RunStatus, RunsFilter } from '@/types/activity'

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

function formatDuration(ms: number | null, sec?: number | null): string {
  if (ms !== undefined && ms !== null) {
    if (ms >= 1000) return `${Math.round(ms / 1000)}с`
    return `${ms}мс`
  }
  if (sec !== undefined && sec !== null) {
    if (sec >= 60) return `${Math.round(sec / 60)}мин`
    return `${Math.round(sec)}с`
  }
  return '—'
}

function formatCost(usd: number): string {
  if (!usd) return '—'
  return `$${usd.toFixed(4)}`
}

function formatNumber(n: number): string {
  return n.toLocaleString('ru-RU')
}

function formatUser(raw: string | null): string {
  if (!raw) return '—'
  return raw.replace(/^user:/, '')
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
  running: 'Выполняется',
}

type SourceTab = 'all' | 'agents' | 'tools'

// ─── status icon ────────────────────────────────────────────────────────────

function StatusIcon({ status, size = 16 }: { status: RunStatus; size?: number }) {
  if (status === 'success') return <CheckCircle2 size={size} className="text-green-600 dark:text-green-400 flex-shrink-0" />
  if (status === 'error') return <XCircle size={size} className="text-red-600 dark:text-red-400 flex-shrink-0" />
  if (status === 'running') return <Loader2 size={size} className="text-blue-500 dark:text-blue-400 flex-shrink-0 animate-spin" />
  return <Clock size={size} className="text-amber-600 dark:text-amber-400 flex-shrink-0" />
}

// ─── agent run row ───────────────────────────────────────────────────────────

function AgentRunRow({ run, expanded, onToggle }: { run: AgentRun; expanded: boolean; onToggle: () => void }) {
  const statusColorClass =
    run.status === 'success' ? 'bg-green-50 border-green-200 text-green-600 dark:bg-green-950 dark:border-green-900 dark:text-green-300'
    : run.status === 'error' ? 'bg-red-50 border-red-200 text-red-600 dark:bg-red-950 dark:border-red-900 dark:text-red-300'
    : 'bg-amber-50 border-amber-200 text-amber-600 dark:bg-amber-950 dark:border-amber-900 dark:text-amber-300'

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3 border-b border-border hover:bg-muted/40 transition-colors cursor-pointer select-none',
          expanded && 'bg-muted/30',
        )}
        onClick={onToggle}
      >
        <StatusIcon status={run.status} />

        {/* Source type badge */}
        <span className="text-[9px] bg-stone-100 text-stone-700 border border-stone-200 dark:bg-stone-800 dark:text-stone-300 dark:border-stone-700 rounded px-1 py-0.5 font-semibold shrink-0">
          АГЕНТ
        </span>

        {/* Agent label */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-foreground truncate">{getAgentLabel(run.agentName)}</p>
          <p className="text-[11px] text-muted-foreground font-mono truncate">{run.agentName}</p>
        </div>

        <span className={cn('hidden sm:inline-flex text-[10px] font-semibold border rounded px-1.5 py-0.5 uppercase tracking-wider', statusColorClass)}>
          {STATUS_LABELS[run.status]}
        </span>
        <p className="text-[12px] text-muted-foreground whitespace-nowrap hidden md:block">{formatDateTime(run.startedAt)}</p>
        <p className="text-[12px] text-muted-foreground w-14 text-right">{formatDuration(run.durationMs)}</p>
        <p className="text-[12px] text-muted-foreground w-20 text-right">{formatCost(run.costUsd)}</p>
        {expanded ? <ChevronUp size={16} className="text-muted-foreground flex-shrink-0" /> : <ChevronDown size={16} className="text-muted-foreground flex-shrink-0" />}
      </div>

      {expanded && (
        <div className="px-4 py-3 bg-muted/20 border-b border-border space-y-2 text-[12px]">
          {run.errorMessage && (
            <div className="bg-red-50 border border-red-200 text-red-700 dark:bg-red-950 dark:border-red-900 dark:text-red-300 rounded-lg px-3 py-2 font-mono text-[11px] whitespace-pre-wrap break-all">
              {run.errorMessage}
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1.5 text-muted-foreground">
            {run.model && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Модель</span>
                <span className="text-foreground font-mono">{run.model}</span>
              </div>
            )}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Токены</span>
              <span className="text-foreground">
                {formatNumber(run.promptTokens)} + {formatNumber(run.completionTokens)} = {formatNumber(run.totalTokens)}
              </span>
            </div>
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Стоимость</span>
              <span className="text-foreground">${run.costUsd.toFixed(6)}</span>
            </div>
            {run.trigger && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Триггер</span>
                <span className="text-foreground">{run.trigger}</span>
              </div>
            )}
            {run.taskType && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Тип задачи</span>
                <span className="text-foreground">{run.taskType}</span>
              </div>
            )}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Запуск</span>
              <span className="text-foreground">{formatDateTime(run.startedAt)}</span>
            </div>
          </div>
          {run.parentRunId && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Parent Run ID: </span>
              <span className="font-mono text-[11px] text-muted-foreground">{run.parentRunId}</span>
            </div>
          )}
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Run ID: </span>
            <span className="font-mono text-[11px] text-muted-foreground">{run.runId}</span>
          </div>
        </div>
      )}
    </>
  )
}

// ─── tool run row ────────────────────────────────────────────────────────────

function ToolRunRow({ run, expanded, onToggle }: { run: ToolRun; expanded: boolean; onToggle: () => void }) {
  const isSkill = run.toolSlug.startsWith('/')
  const statusColorClass =
    run.status === 'success' ? 'bg-green-50 border-green-200 text-green-600 dark:bg-green-950 dark:border-green-900 dark:text-green-300'
    : run.status === 'error' ? 'bg-red-50 border-red-200 text-red-600 dark:bg-red-950 dark:border-red-900 dark:text-red-300'
    : run.status === 'running' ? 'bg-blue-50 border-blue-200 text-blue-600 dark:bg-blue-950 dark:border-blue-900 dark:text-blue-300'
    : 'bg-amber-50 border-amber-200 text-amber-600 dark:bg-amber-950 dark:border-amber-900 dark:text-amber-300'

  const badgeColor = isSkill
    ? 'bg-sky-50 text-sky-600 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900'
    : 'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-900'

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3 border-b border-border hover:bg-muted/40 transition-colors cursor-pointer select-none',
          expanded && 'bg-muted/30',
          run.status === 'error' && !expanded && 'border-l-2 border-l-red-400 dark:border-l-red-500',
        )}
        onClick={onToggle}
      >
        <StatusIcon status={run.status} />

        {/* Source type badge */}
        <span className={cn('text-[9px] border rounded px-1 py-0.5 font-semibold shrink-0', badgeColor)}>
          {isSkill ? 'СКИЛЛ' : 'СЕРВИС'}
        </span>

        {/* Slug + user */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-foreground truncate font-mono">{run.toolSlug}</p>
          <p className="text-[11px] text-muted-foreground truncate">{formatUser(run.triggeredBy)}</p>
        </div>

        {/* Result URL link */}
        {run.resultUrl && (
          <a
            href={run.resultUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="hidden sm:flex items-center gap-1 text-[11px] text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 hover:underline shrink-0"
          >
            Отчёт <ExternalLink size={10} />
          </a>
        )}

        <span className={cn('hidden sm:inline-flex text-[10px] font-semibold border rounded px-1.5 py-0.5 uppercase tracking-wider', statusColorClass)}>
          {STATUS_LABELS[run.status] ?? run.status}
        </span>
        <p className="text-[12px] text-muted-foreground whitespace-nowrap hidden md:block">{formatDateTime(run.startedAt)}</p>
        <p className="text-[12px] text-muted-foreground w-14 text-right">{formatDuration(null, run.durationSec)}</p>
        <p className="text-[12px] text-muted-foreground w-20 text-right">
          {run.itemsProcessed != null ? `${run.itemsProcessed} шт` : '—'}
        </p>
        {expanded ? <ChevronUp size={16} className="text-muted-foreground flex-shrink-0" /> : <ChevronDown size={16} className="text-muted-foreground flex-shrink-0" />}
      </div>

      {expanded && (
        <div className="px-4 py-3 bg-muted/20 border-b border-border space-y-2 text-[12px]">
          {/* Error detail */}
          {run.status === 'error' && (
            <div className="bg-red-50 border border-red-200 dark:bg-red-950 dark:border-red-900 rounded-lg px-3 py-2.5 space-y-1">
              {run.errorStage && (
                <p className="text-[10px] font-semibold text-red-600 dark:text-red-400 uppercase tracking-wider">
                  Этап: {run.errorStage}
                </p>
              )}
              {run.errorMessage && (
                <p className="text-[11px] text-red-700 dark:text-red-300 font-mono whitespace-pre-wrap break-all">
                  {run.errorMessage}
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1.5 text-muted-foreground">
            {/* Triggered by */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Запустил</span>
              <span className="text-foreground">{formatUser(run.triggeredBy)}</span>
            </div>

            {/* Trigger type */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Тип запуска</span>
              <span className="text-foreground">{run.triggerType}</span>
            </div>

            {/* Items */}
            {run.itemsProcessed != null && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Обработано</span>
                <span className="text-foreground">{formatNumber(run.itemsProcessed)} шт</span>
              </div>
            )}

            {/* Period */}
            {(run.periodStart || run.periodEnd) && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Период</span>
                <span className="text-foreground font-mono">
                  {run.periodStart ?? '?'} → {run.periodEnd ?? '?'}
                </span>
              </div>
            )}

            {/* Notes */}
            {run.notes && (
              <div className="col-span-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Заметки</span>
                <span className="text-foreground">{run.notes}</span>
              </div>
            )}

            {/* Duration */}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider block">Запуск</span>
              <span className="text-foreground">{formatDateTime(run.startedAt)}</span>
            </div>

            {/* Version */}
            {run.toolVersion && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Версия</span>
                <span className="text-foreground font-mono">{run.toolVersion}</span>
              </div>
            )}

            {/* Model */}
            {run.modelUsed && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Модель</span>
                <span className="text-foreground font-mono text-[11px]">{run.modelUsed}</span>
              </div>
            )}

            {/* Result URL */}
            {run.resultUrl && (
              <div className="col-span-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider block">Результат</span>
                <a
                  href={run.resultUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 hover:underline inline-flex items-center gap-1 font-mono text-[11px] break-all"
                >
                  {run.resultUrl} <ExternalLink size={10} className="shrink-0" />
                </a>
              </div>
            )}
          </div>

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Run ID: </span>
            <span className="font-mono text-[11px] text-muted-foreground">{run.id}</span>
          </div>
        </div>
      )}
    </>
  )
}

// ─── unified run entry for mixed list ────────────────────────────────────────

type UnifiedEntry =
  | { type: 'agent'; data: AgentRun; sortKey: string }
  | { type: 'tool'; data: ToolRun; sortKey: string }

// ─── main page ──────────────────────────────────────────────────────────────

export function ActivityPage() {
  useDocumentTitle('История запусков')
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([])
  const [toolRuns, setToolRuns] = useState<ToolRun[]>([])
  const [loading, setLoading] = useState(true)
  const [sourceTab, setSourceTab] = useState<SourceTab>('all')
  const [toolLabel, setToolLabel] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<RunStatus | ''>('')
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [agentLimit, setAgentLimit] = useState(50)
  const [toolLimit, setToolLimit] = useState(50)

  const filter = useMemo<RunsFilter>(() => {
    const f: RunsFilter = {}
    if (toolLabel) f.agentNames = LABEL_TO_AGENTS.get(toolLabel) ?? []
    if (statusFilter) f.status = statusFilter as RunStatus
    if (dateFrom) f.dateFrom = dateFrom
    if (dateTo) f.dateTo = `${dateTo}T23:59:59`
    return f
  }, [toolLabel, statusFilter, dateFrom, dateTo])

  // Fetch both sources
  useEffect(() => {
    let cancelled = false
    setLoading(true)

    const fetchAgents = sourceTab !== 'tools'
      ? fetchRuns(filter, agentLimit)
      : Promise.resolve([])

    const toolFilter = {
      status: statusFilter ? (statusFilter as RunStatus) : undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo ? `${dateTo}T23:59:59` : undefined,
    }

    const fetchTools = sourceTab !== 'agents'
      ? fetchToolRuns(toolFilter, toolLimit)
      : Promise.resolve([])

    Promise.all([fetchAgents, fetchTools]).then(([agents, tools]) => {
      if (!cancelled) {
        setAgentRuns(agents)
        setToolRuns(tools)
        setLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [filter, agentLimit, toolLimit, sourceTab, statusFilter, dateFrom, dateTo])

  // Reset on filter change
  useEffect(() => {
    setAgentLimit(50)
    setToolLimit(50)
    setExpandedId(null)
  }, [toolLabel, statusFilter, dateFrom, dateTo, sourceTab])

  // Build unified sorted list
  const unifiedEntries = useMemo<UnifiedEntry[]>(() => {
    const entries: UnifiedEntry[] = []
    if (sourceTab !== 'tools') {
      for (const r of agentRuns) entries.push({ type: 'agent', data: r, sortKey: r.startedAt })
    }
    if (sourceTab !== 'agents') {
      for (const r of toolRuns) entries.push({ type: 'tool', data: r, sortKey: r.startedAt })
    }
    return entries.sort((a, b) => b.sortKey.localeCompare(a.sortKey))
  }, [agentRuns, toolRuns, sourceTab])

  const totalShown = unifiedEntries.length
  const successCount = unifiedEntries.filter((e) =>
    e.type === 'agent' ? e.data.status === 'success' : e.data.status === 'success'
  ).length
  const failCount = unifiedEntries.filter((e) =>
    e.type === 'agent'
      ? e.data.status === 'error' || e.data.status === 'timeout'
      : e.data.status === 'error' || e.data.status === 'timeout'
  ).length

  const agentHasMore = agentRuns.length === agentLimit
  const toolHasMore = toolRuns.length === toolLimit

  function handleLoadMore() {
    if (agentHasMore) setAgentLimit((p) => p + 50)
    if (toolHasMore) setToolLimit((p) => p + 50)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="ОПЕРАЦИИ"
        title="История запусков"
        breadcrumbs={[
          { label: 'Операции', to: '/operations' },
          { label: 'История запусков', to: '/operations/activity' },
        ]}
        description="Агенты, скиллы и сервисы системы Wookiee"
      />

      {/* Source tabs */}
      <div className="flex gap-1 p-1 bg-muted/40 rounded-xl w-fit">
        {([
          { id: 'all', label: 'Все', icon: null },
          { id: 'agents', label: 'Агенты', icon: <Bot size={13} /> },
          { id: 'tools', label: 'Скиллы и сервисы', icon: <Wrench size={13} /> },
        ] as { id: SourceTab; label: string; icon: React.ReactNode }[]).map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setSourceTab(id)}
            className={cn(
              'flex items-center gap-1.5 text-[12px] font-medium px-3 py-1.5 rounded-lg transition-colors',
              sourceTab === id
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Всего запусков', value: totalShown, sub: 'в выборке', cls: 'text-foreground' },
          { label: 'Успешных', value: successCount, sub: `из ${totalShown}`, cls: totalShown > 0 ? 'text-green-600 dark:text-green-400' : 'text-foreground' },
          { label: 'С ошибкой', value: failCount, sub: 'ошибки + таймауты', cls: failCount > 0 ? 'text-red-600 dark:text-red-400' : 'text-foreground' },
        ].map(({ label, value, sub, cls }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-card border border-border rounded-xl p-4 flex flex-wrap gap-4 items-end">
        {/* Tool filter — only for agents tab */}
        {sourceTab !== 'tools' && (
          <div className="flex flex-col gap-1 min-w-[180px]">
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Агент</label>
            <select
              value={toolLabel}
              onChange={(e) => setToolLabel(e.target.value)}
              className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">Все</option>
              {UNIQUE_LABELS.map((label) => (
                <option key={label} value={label}>{label}</option>
              ))}
            </select>
          </div>
        )}

        {/* Status filter */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Статус</label>
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

        {/* Date range */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">От</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">До</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="text-[13px] bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
        </div>

        {(toolLabel || statusFilter || dateFrom || dateTo) && (
          <button
            onClick={() => { setToolLabel(''); setStatusFilter(''); setDateFrom(''); setDateTo('') }}
            className="text-[12px] text-muted-foreground hover:text-foreground transition-colors py-1.5 self-end"
          >
            Сбросить
          </button>
        )}
      </div>

      {/* List */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {/* Column header */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-muted/30">
          <div className="w-4" />
          <div className="w-12 shrink-0" />
          <p className="flex-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            {sourceTab === 'tools' ? 'Инструмент / Пользователь' : 'Агент'}
          </p>
          <p className="hidden sm:block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-16">Статус</p>
          <p className="hidden md:block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-32">Время</p>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-14 text-right">Длит.</p>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-20 text-right">
            {sourceTab === 'tools' ? 'Обработано' : 'Стоимость'}
          </p>
          <div className="w-4" />
        </div>

        {loading && (
          <p className="text-sm text-muted-foreground py-8 text-center">Загружаю запуски...</p>
        )}

        {!loading && unifiedEntries.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-sm text-muted-foreground">Запуски не найдены</p>
            <p className="text-[12px] text-muted-foreground mt-1">Попробуйте изменить фильтры</p>
          </div>
        )}

        {!loading && unifiedEntries.map((entry) => {
          const id = entry.data.id
          const expanded = expandedId === id
          const onToggle = () => setExpandedId((prev) => (prev === id ? null : id))

          if (entry.type === 'agent') {
            return <AgentRunRow key={id} run={entry.data} expanded={expanded} onToggle={onToggle} />
          }
          return <ToolRunRow key={id} run={entry.data} expanded={expanded} onToggle={onToggle} />
        })}
      </div>

      {!loading && (agentHasMore || toolHasMore) && (
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
