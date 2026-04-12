import { cn } from "@/lib/utils"

const metrics = [
  { id: "revenue", label: "По выручке" },
  { id: "orders", label: "По заказам" },
]

const periods = [
  { id: "7", label: "7д" },
  { id: "28", label: "28д" },
  { id: "90", label: "90д" },
  { id: "365", label: "Год" },
]

interface AbcHeaderProps {
  metric: string
  onMetricChange: (metric: string) => void
  period: string
  onPeriodChange: (period: string) => void
}

export function AbcHeader({ metric, onMetricChange, period, onPeriodChange }: AbcHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-lg font-bold">ABC-анализ</h1>
      <div className="flex gap-2">
        <div className="bg-bg-soft border border-border rounded-md p-0.5 flex gap-0.5">
          {metrics.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onMetricChange(m.id)}
              className={cn(
                "px-2.5 py-1 rounded text-[12px] font-medium transition-colors",
                m.id === metric
                  ? "bg-accent text-white"
                  : "bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="bg-bg-soft border border-border rounded-md p-0.5 flex gap-0.5">
          {periods.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => onPeriodChange(p.id)}
              className={cn(
                "px-2.5 py-1 rounded text-[12px] font-medium transition-colors",
                p.id === period
                  ? "bg-accent text-white"
                  : "bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
