import { Settings, Plus, Table2, Clock, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useSupplyStore } from "@/stores/supply"
import type { Entity, SupplyViewMode } from "@/types/supply"
import { cn } from "@/lib/utils"

const entityOptions: { id: Entity; label: string }[] = [
  { id: "ooo", label: "ООО" },
  { id: "ip", label: "ИП" },
]

const viewOptions: { id: SupplyViewMode; label: string; icon: typeof Table2 }[] = [
  { id: "table", label: "Таблица", icon: Table2 },
  { id: "timeline", label: "Таймлайн", icon: Clock },
  { id: "alerts", label: "Алерты", icon: AlertTriangle },
]

interface SupplyHeaderProps {
  onNewOrder: () => void
}

export function SupplyHeader({ onNewOrder }: SupplyHeaderProps) {
  const entity = useSupplyStore((s) => s.entity)
  const viewMode = useSupplyStore((s) => s.viewMode)
  const setEntity = useSupplyStore((s) => s.setEntity)
  const setViewMode = useSupplyStore((s) => s.setViewMode)
  const setSettingsOpen = useSupplyStore((s) => s.setSettingsOpen)

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="flex items-center gap-4">
        <h1 className="text-[22px] font-bold">План поставок</h1>

        {/* Entity toggle */}
        <div className="flex items-center gap-0.5 rounded-lg border border-border p-0.5">
          {entityOptions.map((opt) => (
            <Button
              key={opt.id}
              size="sm"
              variant={entity === opt.id ? "default" : "ghost"}
              className={cn(
                "text-xs",
                entity === opt.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground",
              )}
              onClick={() => setEntity(opt.id)}
            >
              {opt.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* View mode tabs */}
        <div className="flex items-center gap-0.5">
          {viewOptions.map((opt) => {
            const Icon = opt.icon
            const active = viewMode === opt.id
            return (
              <button
                key={opt.id}
                onClick={() => setViewMode(opt.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium transition-colors rounded-md",
                  active
                    ? "text-foreground border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon size={14} />
                {opt.label}
              </button>
            )
          })}
        </div>

        {/* Settings */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setSettingsOpen(true)}
        >
          <Settings size={16} />
        </Button>

        {/* New order */}
        <Button size="sm" onClick={onNewOrder}>
          <Plus size={14} data-icon="inline-start" />
          Новая поставка
        </Button>
      </div>
    </div>
  )
}
