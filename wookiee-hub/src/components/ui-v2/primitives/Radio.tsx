import * as React from "react"
import { cn } from "@/lib/utils"

export interface RadioProps {
  /** Native radio group name — required for grouping. */
  name: string
  /** This radio's value. */
  value: string
  /** Whether this radio is the selected option in its group. */
  checked: boolean
  /** Called when selected — receives this radio's value. */
  onChange: (value: string) => void
  /** Optional inline label rendered to the right. */
  label?: React.ReactNode
  /** Native id — wires up <label htmlFor>. */
  id?: string
  /** Disable interaction + dim the row. */
  disabled?: boolean
  /** Optional className on the outer wrapper. */
  className?: string
}

/**
 * Radio — canonical DS v2 atom (foundation.jsx:247-255).
 *
 * Shape: 14×14 native radio with `accent-[var(--color-text-primary)]`.
 * Identical visual recipe as Checkbox, type="radio".
 */
export const Radio = React.forwardRef<HTMLInputElement, RadioProps>(
  function Radio(
    { name, value, checked, onChange, label, id, disabled, className },
    forwardedRef,
  ) {
    const input = (
      <input
        ref={forwardedRef}
        id={id}
        name={name}
        type="radio"
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange(value)}
        className="w-3.5 h-3.5 accent-[var(--color-text-primary)] cursor-pointer disabled:cursor-not-allowed"
      />
    )

    if (!label) {
      return <span className={cn("inline-flex", disabled && "opacity-50", className)}>{input}</span>
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
        {input}
        <span>{label}</span>
      </label>
    )
  },
)
