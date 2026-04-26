import { useMemo } from "react"
import { Search, Download } from "lucide-react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { useCommsStore } from "@/stores/community"
import { useIntegrationsStore } from "@/stores/integrations"
import { getServiceDef } from "@/config/service-registry"
import { ReviewsFilterPopover } from "@/components/community/reviews-filter-popover"
import { ReviewsSortPopover } from "@/components/community/reviews-sort-popover"
import type { ReviewSource } from "@/types/community"

const sourceTabs: { value: ReviewSource | "all"; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "review", label: "Отзывы" },
  { value: "question", label: "Вопросы" },
  { value: "chat", label: "Чаты" },
]

interface ReviewsHeaderProps {
  className?: string
  activeSource: ReviewSource | "all"
  onSourceChange: (source: ReviewSource | "all") => void
}

export function ReviewsHeader({ className, activeSource, onSourceChange }: ReviewsHeaderProps) {
  const { filters, setFilters } = useCommsStore()
  const allConnections = useIntegrationsStore((s) => s.connections)
  const connections = useMemo(() => allConnections.filter((c) => c.status === "active"), [allConnections])

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-[22px] font-bold">Отзывы и ответы</h1>
        <div className="flex items-center gap-2">
          <select
            value={filters.connectionIds[0] ?? ""}
            onChange={(e) => setFilters({ connectionIds: e.target.value ? [e.target.value] : [] })}
            className="h-8 px-3 rounded-lg border border-border bg-card text-sm focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">Все магазины</option>
            {connections.map((c) => {
              const def = getServiceDef(c.serviceType)
              return (
                <option key={c.id} value={c.id}>
                  {def.label} — {c.name}
                </option>
              )
            })}
          </select>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1 p-1 rounded-lg bg-bg-soft">
          {sourceTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => onSourceChange(tab.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-[13px] font-medium transition-all",
                activeSource === tab.value
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-[280px]">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Поиск по отзывам..."
            value={filters.search}
            onChange={(e) => setFilters({ search: e.target.value })}
            className="pl-8 h-8"
          />
        </div>
        <ReviewsFilterPopover />
        <ReviewsSortPopover />
        <button
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-card text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-bg-hover transition-colors"
          title="Экспорт"
        >
          <Download size={14} />
        </button>
      </div>
    </div>
  )
}
