import * as React from "react"
import { cn } from "@/lib/utils"

export interface ToggleProps {
  /** Controlled on/off state. */
  on: boolean
  /** Change callback — receives the next boolean state. */
  onChange: (next: boolean) => void
  /** Optional inline label rendered to the right of the track. */
  label?: React.ReactNode
  /** Native id for the underlying button (for <label htmlFor>). */
  id?: string
  /** Disable interaction + dim the row. */
  disabled?: boolean
  /** Optional className on the outer wrapper. */
  className?: string
  /** ARIA label when no visible label is rendered. */
  ariaLabel?: string
}

/**
 * Toggle — canonical DS v2 atom (foundation.jsx:257-269).
 *
 * Shape: 36×20 pill track (DS §5 «Toggle — 20×36px») with 16×16 thumb sliding
 * 0.5→4. On-state uses `bg-[var(--color-text-primary)]`; off-state uses
 * literal `bg-stone-200 dark:bg-stone-700` because there is no semantic
 * token for "off-track gray" (intentional raw color per DS §11 escape hatch).
 */
export function Toggle({
  on,
  onChange,
  label,
  id,
  disabled,
  className,
  ariaLabel,
}: ToggleProps) {
  const button = (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={!label && ariaLabel ? ariaLabel : undefined}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={cn(
        "relative inline-flex w-9 h-5 rounded-full transition-colors shrink-0",
        on
          ? "bg-[var(--color-text-primary)]"
          : // DS §11: no semantic token for "off-track gray" — literal raw color intentional.
            "bg-stone-200 dark:bg-stone-700",
        disabled && "cursor-not-allowed",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all",
          on ? "left-4" : "left-0.5",
        )}
        aria-hidden
      />
    </button>
  )

  if (!label) {
    return (
      <span className={cn("inline-flex", disabled && "opacity-50", className)}>
        {button}
      </span>
    )
  }

  return (
    <label
      htmlFor={id}
      className={cn(
        "inline-flex items-center gap-2 text-sm text-secondary cursor-pointer select-none",
        disabled && "opacity-50 cursor-not-allowed",
        className,
      )}
    >
      {button}
      <span>{label}</span>
    </label>
  )
}
