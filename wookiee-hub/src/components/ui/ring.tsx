import { cn } from "@/lib/utils"

export interface RingProps {
  value: number
  max?: number
  size?: number
  strokeWidth?: number
  showLabel?: boolean
  className?: string
}

export function Ring({
  value,
  max = 100,
  size = 48,
  strokeWidth = 4,
  showLabel = true,
  className,
}: RingProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const r = (size - strokeWidth) / 2
  const c = 2 * Math.PI * r
  const offset = c - (pct / 100) * c
  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="currentColor" strokeWidth={strokeWidth} fill="none" className="text-muted opacity-30" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke="currentColor" strokeWidth={strokeWidth} fill="none" className="text-foreground" strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      {showLabel && <span className="absolute text-xs font-medium">{Math.round(pct)}%</span>}
    </div>
  )
}
