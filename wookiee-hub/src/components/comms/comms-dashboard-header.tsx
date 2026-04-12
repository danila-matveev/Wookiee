import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { useIntegrationsStore } from "@/stores/integrations"
import { getServiceDef } from "@/config/service-registry"
import { DateRangePicker } from "@/components/shared/date-range-picker"
import type { DateRange } from "react-day-picker"

interface CommsDashboardHeaderProps {
  className?: string
  selectedConnectionId: string | null
  onConnectionChange: (id: string | null) => void
  dateRange: DateRange | undefined
  onDateRangeChange: (range: DateRange | undefined) => void
}

export function CommsDashboardHeader({
  className,
  selectedConnectionId,
  onConnectionChange,
  dateRange,
  onDateRangeChange,
}: CommsDashboardHeaderProps) {
  const allConnections = useIntegrationsStore((s) => s.connections)
  const connections = useMemo(() => allConnections.filter((c) => c.status === "active"), [allConnections])

  return (
    <div className={cn("flex items-start justify-between gap-4 flex-wrap", className)}>
      <div>
        <h1 className="text-[22px] font-bold">Коммуникации</h1>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Отзывы, вопросы и чаты с маркетплейсов
        </p>
      </div>
      <div className="flex items-center gap-2">
        <DateRangePicker value={dateRange} onChange={onDateRangeChange} />
        <select
          value={selectedConnectionId ?? ""}
          onChange={(e) => onConnectionChange(e.target.value || null)}
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
  )
}
