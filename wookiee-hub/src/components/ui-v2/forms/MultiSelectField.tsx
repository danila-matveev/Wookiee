import * as React from "react"
import { cn } from "@/lib/utils"
import { FieldWrap } from "./FieldWrap"
import type { SelectOption } from "./SelectField"
import type { CatalogLevel } from "../primitives"

interface NormalisedOption {
  value: string
  label: string
  disabled?: boolean
}

function normalise(opt: SelectOption): NormalisedOption {
  if ("value" in opt) {
    return { value: opt.value, label: opt.label, disabled: opt.disabled }
  }
  return { value: String(opt.id), label: opt.nazvanie, disabled: opt.disabled }
}

export interface MultiSelectFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  /** Catalog-hierarchy marker rendered inline with the label (M/V/A/S). */
  level?: CatalogLevel
  labelAddon?: React.ReactNode

  value: string[]
  onChange: (next: string[]) => void
  options: SelectOption[]

  disabled?: boolean
  className?: string
}

/**
 * MultiSelectField — inline chips-toggle.
 *
 * Canonical contract (foundation.jsx:514-533, DS §6):
 * «MultiSelectField — chips-toggles, не dropdown». All options render as
 * togglable buttons in a flex-wrap row. Active = inverted (primary bg, surface text).
 *
 * Accepts both option shapes — semantic `{value, label}` and WB-style
 * `{id, nazvanie}` — normalised internally.
 */
export function MultiSelectField({
  id,
  label,
  hint,
  error,
  required,
  level,
  labelAddon,
  value,
  onChange,
  options,
  disabled,
  className,
}: MultiSelectFieldProps) {
  const normalised = React.useMemo(() => options.map(normalise), [options])

  const toggle = (v: string) => {
    if (value.includes(v)) onChange(value.filter((x) => x !== v))
    else onChange([...value, v])
  }

  return (
    <FieldWrap
      id={id}
      label={label}
      hint={hint}
      error={error}
      required={required}
      level={level}
      labelAddon={labelAddon}
      className={className}
    >
      <div
        id={id}
        role="group"
        aria-label={typeof label === "string" ? label : undefined}
        className="flex flex-wrap gap-1.5"
      >
        {normalised.map((opt) => {
          const active = value.includes(opt.value)
          return (
            <button
              key={opt.value}
              type="button"
              role="checkbox"
              aria-checked={active}
              disabled={disabled || opt.disabled}
              onClick={() => toggle(opt.value)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-md transition-colors",
                "outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
                active
                  ? "bg-[var(--color-text-primary)] text-[var(--color-surface)]"
                  : "border border-default text-secondary hover:bg-surface-muted",
                (disabled || opt.disabled) && "opacity-50 cursor-not-allowed",
              )}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </FieldWrap>
  )
}
