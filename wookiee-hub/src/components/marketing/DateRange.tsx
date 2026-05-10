import { Calendar } from "lucide-react"

export interface DateRangeProps {
  from: string
  to: string
  onChange: (from: string, to: string) => void
  min?: string
  max?: string
}

export function DateRange({ from, to, onChange, min, max }: DateRangeProps) {
  // Auto-swap if from > to
  const handleFrom = (v: string) => onChange(v, v > to ? v : to)
  const handleTo   = (v: string) => onChange(v < from ? v : from, v)
  const inputCls = "border border-border rounded-md px-2 py-1 text-xs tabular-nums text-foreground/80 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring bg-card w-[120px]"

  return (
    <div className="flex items-center gap-1.5">
      <Calendar className="w-3.5 h-3.5 text-muted-foreground shrink-0" aria-hidden />
      <input
        type="date" value={from} min={min} max={to} onChange={(e) => handleFrom(e.target.value)}
        className={inputCls} aria-label="Дата начала"
      />
      <span className="text-muted-foreground/50 text-xs">→</span>
      <input
        type="date" value={to} min={from} max={max} onChange={(e) => handleTo(e.target.value)}
        className={inputCls} aria-label="Дата окончания"
      />
    </div>
  )
}
