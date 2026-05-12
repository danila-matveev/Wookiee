import * as React from "react"
import { cn } from "@/lib/utils"

export interface SliderProps {
  /** Controlled numeric value. */
  value: number
  /** Change callback — receives the next number. */
  onChange: (next: number) => void
  /** Min bound (default 0). */
  min?: number
  /** Max bound (default 100). */
  max?: number
  /** Step increment (default 1). */
  step?: number
  /** Suffix unit shown next to the value display (e.g. "%", "₽"). */
  suffix?: string
  /** Optional label rendered above the slider row. */
  label?: React.ReactNode
  /** Native id — wires up <label htmlFor>. */
  id?: string
  /** Disable interaction + dim the row. */
  disabled?: boolean
  /** Optional className on the outer wrapper. */
  className?: string
}

/**
 * Slider — canonical DS v2 atom (foundation.jsx:271-279).
 *
 * Native `<input type="range">` with `accent-[var(--color-text-primary)]`.
 * Row layout: slider `flex-1`, value display `text-sm tabular-nums w-12 text-right`.
 */
export function Slider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  suffix = "",
  label,
  id,
  disabled,
  className,
}: SliderProps) {
  return (
    <div className={cn("w-full space-y-1", className)}>
      {label ? (
        <label
          htmlFor={id}
          className="text-[11px] uppercase tracking-wider font-medium text-label"
        >
          {label}
        </label>
      ) : null}
      <div className={cn("flex items-center gap-3 w-full", disabled && "opacity-50")}>
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 accent-[var(--color-text-primary)] cursor-pointer disabled:cursor-not-allowed"
        />
        <span className="text-sm tabular-nums w-12 text-right text-secondary">
          {value}
          {suffix}
        </span>
      </div>
    </div>
  )
}
