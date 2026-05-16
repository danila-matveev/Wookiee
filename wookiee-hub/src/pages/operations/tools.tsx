import { useEffect, useMemo } from 'react'
import { useOperationsStore, filterTools } from '@/stores/operations'
import { fetchTools } from '@/lib/tools-service'
import { ToolCard } from '@/components/operations/tool-card'
import { ToolFilters } from '@/components/operations/tool-filters'
import { ToolDetailPanel } from '@/components/operations/tool-detail-panel'
import { PageHeader } from '@/components/layout/page-header'
import type { OperationsTool, ToolCategory, ToolCategoryFilter } from '@/types/tool'

const CATEGORY_LABELS: Record<ToolCategory, string> = {
  analytics:  'Аналитика',
  infra:      'Инфраструктура',
  content:    'Контент',
  publishing: 'Публикация',
  team:       'Команда',
  planning:   'Планирование',
}
const CATEGORY_ORDER: ToolCategory[] = ['analytics', 'infra', 'content', 'publishing', 'team', 'planning']

export function ToolsPage() {
  const {
    tools, loading, categoryFilter, searchQuery, selectedTool,
    setTools, setLoading, setCategoryFilter, setSearchQuery, setSelectedTool,
  } = useOperationsStore()

  useEffect(() => {
    setLoading(true)
    fetchTools().then((data) => { setTools(data); setLoading(false) })
  }, [])

  const filtered = useMemo(
    () => filterTools(tools, categoryFilter, searchQuery),
    [tools, categoryFilter, searchQuery]
  )

  const counts = useMemo(() => {
    const result: Partial<Record<ToolCategoryFilter, number>> = { all: tools.length }
    for (const tool of tools) {
      result[tool.category] = (result[tool.category] ?? 0) + 1
    }
    return result
  }, [tools])

  const grouped = useMemo(() => {
    const map = new Map<ToolCategory, OperationsTool[]>()
    for (const tool of filtered) {
      const list = map.get(tool.category) ?? []
      list.push(tool)
      map.set(tool.category, list)
    }
    return CATEGORY_ORDER
      .filter((cat) => map.has(cat))
      .map((cat) => ({ category: cat, tools: map.get(cat)! }))
  }, [filtered])

  const activeCount = tools.filter(t => t.status === 'active').length
  const errorCount = tools.filter(t => t.lastStatus === 'error').length

  const lastRunDisplay = useMemo(() => {
    const dates = tools.filter(t => t.lastRunAt).map(t => t.lastRunAt!)
    if (dates.length === 0) return '—'
    const latest = dates.reduce((a, b) => a > b ? a : b)
    const diff = Date.now() - new Date(latest).getTime()
    const h = Math.floor(diff / 3_600_000)
    if (h < 1) return 'только что'
    if (h < 24) return `${h}ч назад`
    return `${Math.floor(h / 24)}д назад`
  }, [tools])

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="Operations"
        title="Каталог инструментов"
        breadcrumbs={[
          { label: 'Operations', to: '/operations' },
          { label: 'Tools', to: '/operations/tools' },
        ]}
        description="Все инструменты системы Wookiee — агенты, сервисы, скиллы, cron-задачи"
      />

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Всего тулзов',     value: tools.length,   sub: 'в каталоге',         cls: 'text-foreground' },
          { label: 'Активных',         value: activeCount,     sub: `из ${tools.length}`,  cls: 'text-green-600 dark:text-green-400' },
          { label: 'С ошибкой',        value: errorCount,      sub: 'last_status = error', cls: errorCount > 0 ? 'text-red-600 dark:text-red-400' : 'text-foreground' },
          { label: 'Последний запуск', value: lastRunDisplay,  sub: 'по данным каталога',  cls: 'text-foreground' },
        ].map(({ label, value, sub, cls }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <ToolFilters
        activeCategory={categoryFilter}
        searchQuery={searchQuery}
        counts={counts}
        onCategoryChange={setCategoryFilter}
        onSearchChange={setSearchQuery}
      />

      {/* Loading */}
      {loading && (
        <p className="text-sm text-muted-foreground py-8 text-center">Загружаю тулзы...</p>
      )}

      {/* Grouped grid */}
      {!loading && grouped.map(({ category, tools: catTools }) => (
        <div key={category}>
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              {CATEGORY_LABELS[category]}
            </h2>
            <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
              {catTools.length}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {catTools.map((tool) => (
              <ToolCard key={tool.slug} tool={tool} onSelect={setSelectedTool} />
            ))}
          </div>
        </div>
      ))}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-sm text-muted-foreground">Тулзы не найдены</p>
        </div>
      )}

      {/* Add new tool instruction */}
      {!loading && (
        <div className="border border-dashed border-border rounded-xl p-4 text-center">
          <p className="text-[13px] font-medium text-foreground">Добавить новый инструмент в каталог</p>
          <p className="text-[12px] text-muted-foreground mt-1">
            Запустите{' '}
            <code className="font-mono bg-muted text-foreground px-1 py-0.5 rounded">/tool-register</code>
            {' '}в Claude Code — скилл заведёт запись в Supabase и обновит каталог
          </p>
        </div>
      )}

      {/* Detail Panel */}
      {selectedTool && (
        <ToolDetailPanel tool={selectedTool} onClose={() => setSelectedTool(null)} />
      )}
    </div>
  )
}
