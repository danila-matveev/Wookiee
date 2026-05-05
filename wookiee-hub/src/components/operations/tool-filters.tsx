import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolCategoryFilter } from '@/types/tool'

const CATEGORIES: { value: ToolCategoryFilter; label: string }[] = [
  { value: 'all',        label: 'Все' },
  { value: 'analytics',  label: 'Аналитика' },
  { value: 'infra',      label: 'Инфраструктура' },
  { value: 'content',    label: 'Контент' },
  { value: 'publishing', label: 'Публикация' },
  { value: 'team',       label: 'Команда' },
  { value: 'planning',   label: 'Планирование' },
]

interface ToolFiltersProps {
  activeCategory: ToolCategoryFilter
  searchQuery: string
  counts: Partial<Record<ToolCategoryFilter, number>>
  onCategoryChange: (category: ToolCategoryFilter) => void
  onSearchChange: (query: string) => void
}

export function ToolFilters({
  activeCategory,
  searchQuery,
  counts,
  onCategoryChange,
  onSearchChange,
}: ToolFiltersProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {CATEGORIES.map(({ value, label }) => {
        const count = counts[value] ?? 0
        if (value !== 'all' && count === 0) return null
        return (
          <button
            key={value}
            onClick={() => onCategoryChange(value)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors',
              activeCategory === value
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:border-primary/40 hover:text-foreground'
            )}
          >
            {label}
            {value !== 'all' && (
              <span className="ml-1 opacity-60">{count}</span>
            )}
          </button>
        )
      })}

      <div className="ml-auto flex items-center gap-2 border border-border rounded-lg px-3 py-1.5 bg-card min-w-[180px]">
        <Search size={13} className="text-muted-foreground shrink-0" />
        <input
          type="text"
          placeholder="Поиск тулзов..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="text-[12px] bg-transparent outline-none text-foreground placeholder:text-muted-foreground w-full"
        />
      </div>
    </div>
  )
}
