import { cn } from '@/lib/utils'
import type { OperationsTool } from '@/types/tool'

const TYPE_LABELS: Record<string, string> = {
  skill:   'Скилл',
  service: 'Сервис',
  cron:    'Cron',
  script:  'Скрипт',
}

const TYPE_CLASSES: Record<string, string> = {
  skill:   'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
  service: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  cron:    'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  script:  'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
}

function getStatusDot(tool: OperationsTool): string {
  if (tool.lastStatus === 'error') return 'bg-red-500'
  if (tool.status === 'deprecated') return 'bg-amber-500'
  if (tool.status === 'draft') return 'bg-gray-400'
  if (tool.status === 'archived') return 'bg-gray-300'
  return 'bg-green-500'
}

function formatLastRun(iso: string | null): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'только что'
  if (h < 24) return `${h}ч назад`
  const d = Math.floor(h / 24)
  return `${d}д назад`
}

interface ToolCardProps {
  tool: OperationsTool
  onSelect: (tool: OperationsTool) => void
}

export function ToolCard({ tool, onSelect }: ToolCardProps) {
  return (
    <article
      role="article"
      onClick={() => onSelect(tool)}
      className={cn(
        'bg-card rounded-xl p-4 cursor-pointer hover:shadow-sm transition-all border',
        tool.lastStatus === 'error'
          ? 'border-red-300 bg-red-50/30 hover:border-red-400 dark:border-red-900 dark:bg-red-950/30 dark:hover:border-red-800'
          : 'border-border hover:border-primary/40'
      )}
    >
      <div className="flex items-start justify-between mb-1.5">
        <div className="min-w-0 flex-1 mr-2">
          <p className="font-mono text-[13px] font-semibold text-foreground truncate">
            {tool.name}
          </p>
          {tool.nameRu && (
            <p className="text-[12px] text-muted-foreground mt-0.5 truncate">{tool.nameRu}</p>
          )}
        </div>
        <span
          data-status={tool.status}
          data-last-status={tool.lastStatus ?? 'none'}
          className={cn('w-2 h-2 rounded-full shrink-0 mt-1.5', getStatusDot(tool))}
        />
      </div>

      {tool.description && (
        <p className="text-[12px] text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
          {tool.description}
        </p>
      )}

      <div className="flex items-center gap-2">
        <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', TYPE_CLASSES[tool.type] ?? 'bg-muted text-muted-foreground')}>
          {TYPE_LABELS[tool.type] ?? tool.type}
        </span>
        <span className="text-[11px] text-muted-foreground ml-auto">
          {formatLastRun(tool.lastRunAt)}
        </span>
      </div>
    </article>
  )
}
