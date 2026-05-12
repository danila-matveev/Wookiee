import * as React from "react"
import { cn } from "@/lib/utils"

export type RingVariant = "default" | "success" | "warning" | "danger" | "info"

/**
 * `inputScale` — explicit because canonical (foundation.jsx:402) takes
 * value in 0..1 ("fraction") and CompletenessRing legacy adapter passes 0..100
 * ("percent"). Default = canonical ("fraction"). Pass `inputScale="percent"`
 * to keep the legacy 0..100 contract.
 */
export type RingInputScale = "fraction" | "percent"
export type RingSize = "sm" | "md" | "lg"

export interface RingProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  /** number = px, preset = sm 32 / md 40 / lg 56. Default = 32. */
  size?: number | RingSize
  strokeWidth?: number
  variant?: RingVariant
  inputScale?: RingInputScale
  label?: React.ReactNode
}

const strokeColor: Record<RingVariant, string> = {
  default: "var(--color-text-primary)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  info: "var(--color-info)",
}

const sizePresets: Record<RingSize, number> = {
  sm: 32,
  md: 40,
  lg: 56,
}

// Canonical thresholds (foundation.jsx:403) are expressed on 0..1.
// emerald ≥ 0.85, blue ≥ 0.6, amber ≥ 0.4, else rose (danger).
function pickVariant(fraction: number, variant?: RingVariant): RingVariant {
  if (variant) return variant
  if (fraction >= 0.85) return "success"
  if (fraction >= 0.6) return "info"
  if (fraction >= 0.4) return "warning"
  return "danger"
}

export const Ring = React.forwardRef<HTMLDivElement, RingProps>(function Ring(
  {
    value,
    size = 32,
    strokeWidth = 3,
    variant,
    inputScale = "fraction",
    label,
    className,
    ...props
  },
  ref,
) {
  const resolvedSize = typeof size === "number" ? size : sizePresets[size]
  // Normalize to 0..1 regardless of input scale.
  const fraction =
    inputScale === "percent"
      ? Math.max(0, Math.min(1, value / 100))
      : Math.max(0, Math.min(1, value))
  const v = pickVariant(fraction, variant)
  const r = (resolvedSize - strokeWidth) / 2
  const c = 2 * Math.PI * r
  const offset = c * (1 - fraction)

  return (
    <div
      ref={ref}
      role="progressbar"
      aria-valuenow={Math.round(fraction * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: resolvedSize, height: resolvedSize }}
      {...props}
    >
      <svg width={resolvedSize} height={resolvedSize} className="-rotate-90">
        <circle
          cx={resolvedSize / 2}
          cy={resolvedSize / 2}
          r={r}
          fill="none"
          stroke="var(--color-border-default)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={resolvedSize / 2}
          cy={resolvedSize / 2}
          r={r}
          fill="none"
          stroke={strokeColor[v]}
          strokeWidth={strokeWidth}
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-200"
        />
      </svg>
      {label !== undefined && (
        <span className="absolute inset-0 flex items-center justify-center text-xs tabular-nums text-primary">
          {label}
        </span>
      )}
    </div>
  )
})
