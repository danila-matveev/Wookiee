import * as React from "react"
import { cn } from "@/lib/utils"

// Canonical palette — foundation.jsx:383. We accept both canonical color
// names and the legacy semantic aliases that were already in the codebase.
export type ProgressColor = "stone" | "emerald" | "blue" | "amber" | "red"
export type ProgressVariant = ProgressColor | "default" | "success" | "warning" | "danger"

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  /** Canonical name is `color`. `variant` kept as alias. */
  color?: ProgressVariant
  variant?: ProgressVariant
  label?: string
  showValue?: boolean
  compact?: boolean
}

const aliasToColor: Record<Exclude<ProgressVariant, ProgressColor>, ProgressColor> = {
  default: "stone",
  success: "emerald",
  warning: "amber",
  danger: "red",
}

const fillColor: Record<ProgressColor, string> = {
  stone: "bg-[var(--color-text-primary)]",
  emerald: "bg-[var(--color-success)]",
  blue: "bg-[var(--color-info)]",
  amber: "bg-[var(--color-warning)]",
  red: "bg-[var(--color-danger)]",
}

function resolveColor(input: ProgressVariant | undefined): ProgressColor {
  if (!input) return "stone"
  if (input in aliasToColor) return aliasToColor[input as keyof typeof aliasToColor]
  return input as ProgressColor
}

export const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  function ProgressBar(
    {
      value,
      color,
      variant,
      label,
      showValue = false,
      compact = false,
      className,
      ...props
    },
    ref,
  ) {
    const clamped = Math.max(0, Math.min(100, value))
    const resolved = resolveColor(color ?? variant)

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
            className={cn("h-full transition-all duration-200 rounded-full", fillColor[resolved])}
            style={{ width: `${clamped}%` }}
          />
        </div>
      </div>
    )
  },
)
