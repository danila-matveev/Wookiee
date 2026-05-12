import * as React from "react"
import { Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface TimePickerProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  /** Time in "HH:MM" format, or empty/null when not yet chosen. */
  value: string | null
  /** Called with the next "HH:MM" string. Empty string clears. */
  onChange: (next: string) => void

  /** Earliest hour to include in options (default 8 — DS canonical 08:00). */
  minHour?: number
  /** Latest hour to include in options inclusive (default 21 — DS canonical 21:00). */
  maxHour?: number
  /** Step in minutes (default 30 — DS canonical 30-min slots). */
  stepMinutes?: 15 | 30 | 60
  placeholder?: string
  disabled?: boolean
  className?: string
  name?: string
}

function pad(n: number): string {
  return String(n).padStart(2, "0")
}

function buildOptions(minHour: number, maxHour: number, stepMinutes: number): string[] {
  const opts: string[] = []
  for (let h = minHour; h <= maxHour; h++) {
    for (let m = 0; m < 60; m += stepMinutes) {
      opts.push(`${pad(h)}:${pad(m)}`)
    }
  }
  return opts
}

/**
 * TimePicker — canonical DS v2 form field (foundation.jsx:634-649).
 *
 * Native `<select>` styled to match SelectField. Default options span
 * 08:00 → 21:00 in 30-minute steps (27 options) per the brief.
 * Wrapped in FieldWrap so it integrates with the form layout system.
 */
export function TimePicker({
  id,
  label,
  hint,
  error,
  required,
  labelAddon,
  value,
  onChange,
  minHour = 8,
  maxHour = 21,
  stepMinutes = 30,
  placeholder = "Выбрать время",
  disabled,
  className,
  name,
}: TimePickerProps) {
  const aria = describedBy(id, hint, error)
  const options = React.useMemo(
    () => buildOptions(minHour, maxHour, stepMinutes),
    [minHour, maxHour, stepMinutes],
  )

  return (
    <FieldWrap
      id={id}
      label={label}
      hint={hint}
      error={error}
      required={required}
      labelAddon={labelAddon}
      className={className}
    >
      <div className="relative">
        <select
          id={id}
          name={name}
          value={value ?? ""}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={aria}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            inputBase,
            inputSizeMd,
            "appearance-none pr-8 text-left tabular-nums",
            !value && "text-muted",
            error && inputError,
          )}
        >
          <option value="">{placeholder}</option>
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <Clock
          className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
          aria-hidden
        />
      </div>
    </FieldWrap>
  )
}
