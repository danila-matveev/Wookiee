import { cn } from "@/lib/utils"

const periods = [
  { id: "7", label: "7д" },
  { id: "28", label: "28д" },
  { id: "90", label: "90д" },
  { id: "365", label: "Год" },
]

interface AnalyticsHeaderProps {
  title: string
  period: string
  onPeriodChange: (period: string) => void
}

export function AnalyticsHeader({ title, period, onPeriodChange }: AnalyticsHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-lg font-bold">{title}</h1>
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
  )
}
