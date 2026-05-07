import { cn } from "@/lib/utils"

interface CompletenessRingProps {
  /**
   * 0..1 (доля) или 0..100 (процент). Авто-detect: если value > 1 → считаем процентом.
   */
  value: number
  /** px, default 28 (MVP default). 16 is small inline variant. */
  size?: number
  /** Hide percent text, keep only ring. */
  hideLabel?: boolean
  className?: string
}

/**
 * CompletenessRing — SVG-кольцо с процентом заполненности.
 * Цвета по порогам (соответствует MVP wookiee_matrix_mvp_v4.jsx):
 *   <30 red, 30-69 amber, 70-89 blue, 90+ green.
 */
export function CompletenessRing({
  value, size = 28, hideLabel = false, className,
}: CompletenessRingProps) {
  const fraction = Math.max(0, Math.min(1, value > 1 ? value / 100 : value))
  const pct = fraction * 100
  const radius = (size - 4) / 2
  const circ = 2 * Math.PI * radius
  const dash = circ * fraction
  // MVP thresholds: <30 red, 30-69 amber, 70-89 blue, 90+ green
  const color =
    pct >= 90 ? "#10B981"
    : pct >= 70 ? "#3B82F6"
    : pct >= 30 ? "#F59E0B"
    : "#EF4444"

  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <svg width={size} height={size} className="-rotate-90 shrink-0">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke="#E7E5E4" strokeWidth="2" fill="none"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke={color} strokeWidth="2" fill="none"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      {!hideLabel && (
        <span className="text-xs text-stone-500 tabular-nums">{Math.round(pct)}%</span>
      )}
    </div>
  )
}
