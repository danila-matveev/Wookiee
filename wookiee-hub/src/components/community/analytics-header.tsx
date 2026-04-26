import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { useIntegrationsStore } from "@/stores/integrations"
import { getServiceDef } from "@/config/service-registry"

const periods = [
  { id: "7", label: "7д" },
  { id: "28", label: "28д" },
  { id: "90", label: "90д" },
  { id: "365", label: "Год" },
]

interface AnalyticsHeaderProps {
  activePeriod: string
  onPeriodChange: (period: string) => void
  selectedConnectionId: string | null
  onConnectionChange: (id: string | null) => void
}

export function CommsAnalyticsHeader({
  activePeriod,
  onPeriodChange,
  selectedConnectionId,
  onConnectionChange,
}: AnalyticsHeaderProps) {
  const allConnections = useIntegrationsStore((s) => s.connections)
  const connections = useMemo(() => allConnections.filter((c) => c.status === "active"), [allConnections])

  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      <h1 className="text-lg font-bold">Аналитика коммуникаций</h1>
      <div className="flex items-center gap-2">
        <div className="bg-bg-soft border border-border rounded-md p-0.5 flex gap-0.5">
          {periods.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => onPeriodChange(p.id)}
              className={cn(
                "px-2.5 py-1 rounded text-[12px] font-medium transition-colors",
                p.id === activePeriod
                  ? "bg-accent text-white"
                  : "bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
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
