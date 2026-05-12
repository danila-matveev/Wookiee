import { cn } from "@/lib/utils"
import { Ring, type RingVariant } from "@/components/ui-v2/primitives"

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
 *
 * Тонкий wrapper над `<Ring>` из ui-v2.  Caller-side остаётся прежний
 * (`value: 0..1 | 0..100`, `size: px`, `hideLabel`).
 *
 * Пороги цветов (MVP wookiee_matrix_mvp_v4.jsx):
 *   <30 danger, 30-69 warning, 70-89 info, 90+ success.
 */
export function CompletenessRing({
  value, size = 28, hideLabel = false, className,
}: CompletenessRingProps) {
  const fraction = Math.max(0, Math.min(1, value > 1 ? value / 100 : value))
  const pct = fraction * 100

  // MVP thresholds: <30 danger, 30-69 warning, 70-89 info, 90+ success.
  const variant: RingVariant =
    pct >= 90 ? "success"
    : pct >= 70 ? "info"
    : pct >= 30 ? "warning"
    : "danger"

  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <Ring
        value={pct}
        size={size}
        strokeWidth={2}
        variant={variant}
      />
      {!hideLabel && (
        <span className="text-xs text-muted tabular-nums">{Math.round(pct)}%</span>
      )}
    </div>
  )
}
