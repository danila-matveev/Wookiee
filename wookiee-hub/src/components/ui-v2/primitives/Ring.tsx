import * as React from "react"
import { cn } from "@/lib/utils"

export type RingVariant = "default" | "success" | "warning" | "danger" | "info"

export interface RingProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  size?: number
  strokeWidth?: number
  variant?: RingVariant
  label?: React.ReactNode
}

const strokeColor: Record<RingVariant, string> = {
  default: "var(--color-text-primary)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  info: "var(--color-info)",
}

function pickVariant(value: number, variant?: RingVariant): RingVariant {
  if (variant) return variant
  if (value >= 85) return "success"
  if (value >= 60) return "info"
  if (value >= 40) return "warning"
  return "danger"
}

export const Ring = React.forwardRef<HTMLDivElement, RingProps>(function Ring(
  { value, size = 32, strokeWidth = 3, variant, label, className, ...props },
  ref,
) {
  const clamped = Math.max(0, Math.min(100, value))
  const v = pickVariant(clamped, variant)
  const r = (size - strokeWidth) / 2
  const c = 2 * Math.PI * r
  const offset = c * (1 - clamped / 100)

  return (
    <div
      ref={ref}
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      {...props}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-border-default)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
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
