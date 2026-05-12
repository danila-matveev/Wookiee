import * as React from "react"
import { cn } from "@/lib/utils"

export type ProgressVariant = "default" | "success" | "warning" | "danger"

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  variant?: ProgressVariant
  label?: string
  showValue?: boolean
  compact?: boolean
}

const fillColor: Record<ProgressVariant, string> = {
  default: "bg-[var(--color-text-primary)]",
  success: "bg-[var(--color-success)]",
  warning: "bg-[var(--color-warning)]",
  danger: "bg-[var(--color-danger)]",
}

export const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  function ProgressBar(
    { value, variant = "default", label, showValue = false, compact = false, className, ...props },
    ref,
  ) {
    const clamped = Math.max(0, Math.min(100, value))

    return (
      <div ref={ref} className={cn("w-full", className)} {...props}>
        {(label || showValue) && (
          <div className="flex items-center justify-between mb-1">
            {label && <span className="text-xs text-secondary">{label}</span>}
            {showValue && (
              <span className="text-xs tabular-nums text-muted">{Math.round(clamped)}%</span>
            )}
          </div>
        )}
        <div
          role="progressbar"
          aria-valuenow={Math.round(clamped)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
          className={cn(
            "w-full overflow-hidden rounded-full bg-surface-muted",
            compact ? "h-1" : "h-1.5",
          )}
        >
          <div
            className={cn("h-full transition-all duration-200 rounded-full", fillColor[variant])}
            style={{ width: `${clamped}%` }}
          />
        </div>
      </div>
    )
  },
)
