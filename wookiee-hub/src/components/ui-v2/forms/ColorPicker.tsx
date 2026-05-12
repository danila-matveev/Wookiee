import * as React from "react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface ColorPickerProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  /** Current hex color (e.g. "#7C3AED"). */
  value: string
  /** Called with the next hex string. */
  onChange: (hex: string) => void

  /** Optional override palette. Defaults to the canonical 9-color set. */
  palette?: string[]
  disabled?: boolean
  className?: string
}

/**
 * Canonical 9-color palette (per R3 brief — translated to semantic Tailwind tones).
 * Each is the brand 600-tone equivalent for that hue family.
 */
const DEFAULT_PALETTE = [
  "#1C1917", // stone-900
  "#E11D48", // rose-600
  "#D97706", // amber-600
  "#059669", // emerald-600
  "#2563EB", // blue-600
  "#7C3AED", // violet-600 (DS spec uses violet for purple)
  "#0D9488", // teal-600
  "#4F46E5", // indigo-600
  "#DB2777", // pink-600
]

function normalizeHex(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ""
  return trimmed.startsWith("#") ? trimmed : `#${trimmed}`
}

/**
 * ColorPicker — canonical DS v2 form field (foundation.jsx:727-745).
 *
 * 9-swatch palette row (24×24 buttons) + mono hex `<input>` for custom values.
 * Wrapped in FieldWrap. Selected swatch carries a thick outer ring per
 * the brief recipe.
 */
export function ColorPicker({
  id,
  label,
  hint,
  error,
  required,
  labelAddon,
  value,
  onChange,
  palette = DEFAULT_PALETTE,
  disabled,
  className,
}: ColorPickerProps) {
  const aria = describedBy(id, hint, error)
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
      <div className="flex items-center gap-2">
        <div className="flex flex-wrap gap-1.5 flex-1">
          {palette.map((c) => {
            const active = value.toLowerCase() === c.toLowerCase()
            return (
              <button
                key={c}
                type="button"
                disabled={disabled}
                onClick={() => onChange(c)}
                aria-label={`Цвет ${c}`}
                aria-pressed={active}
                className={cn(
                  "w-6 h-6 rounded ring-1 ring-inset transition-transform",
                  // Outer ring + offset on selected, neutral ring otherwise.
                  active
                    ? "ring-2 ring-offset-2 ring-offset-[var(--color-surface)] ring-[var(--color-text-primary)]"
                    : // DS §11: literal stone for neutral swatch border (no semantic token).
                      "ring-stone-200 dark:ring-stone-700 hover:scale-110",
                  disabled && "opacity-50 cursor-not-allowed",
                )}
                style={{ background: c }}
              />
            )
          })}
        </div>
        <input
          id={id}
          type="text"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(normalizeHex(e.target.value))}
          placeholder="#000000"
          aria-invalid={error ? true : undefined}
          aria-describedby={aria}
          className={cn(
            inputBase,
            inputSizeMd,
            "w-24 font-mono text-xs",
            error && inputError,
          )}
        />
      </div>
    </FieldWrap>
  )
}
