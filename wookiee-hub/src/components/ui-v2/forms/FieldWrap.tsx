import * as React from "react"
import { cn } from "@/lib/utils"
import { LevelBadge, type CatalogLevel } from "../primitives"

export interface FieldWrapProps {
  /** id of the underlying control — wires up <label htmlFor> */
  id: string
  /** UPPERCASE label rendered above the control */
  label?: React.ReactNode
  /** Hint text below the control (muted) */
  hint?: React.ReactNode
  /** Error text below the control (danger). Overrides hint when present. */
  error?: React.ReactNode
  /** Marks field as required — renders a small "*" */
  required?: boolean
  /**
   * Catalog-hierarchy marker rendered inline next to the label.
   * Canonical (foundation.jsx:465-477) — `<LevelBadge level={level} />`.
   */
  level?: CatalogLevel
  /** Optional right-aligned slot in the label row (rendered after LevelBadge). */
  labelAddon?: React.ReactNode
  /** Optional className applied to the outer wrapper */
  className?: string
  /** The control itself */
  children: React.ReactNode
}

/**
 * FieldWrap — layout shell for any form control.
 * Renders: label row → control → hint/error.
 *
 * Uses semantic DS v2 tokens only (`text-label`, `text-muted`, `text-danger`).
 * Theme switches automatically via [data-theme='dark'] on <html>.
 */
export const FieldWrap = React.forwardRef<HTMLDivElement, FieldWrapProps>(
  function FieldWrap(
    { id, label, hint, error, required, level, labelAddon, className, children },
    ref,
  ) {
    const describedById = error ? `${id}-error` : hint ? `${id}-hint` : undefined
    const hasLabelRow = label || level || labelAddon
    return (
      <div ref={ref} className={cn("space-y-1.5", className)}>
        {hasLabelRow && (
          <div className="flex items-center justify-between gap-2">
            {label ? (
              <label
                htmlFor={id}
                className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-medium text-label"
              >
                <span>
                  {label}
                  {required ? (
                    <span aria-hidden className="ml-0.5 text-danger">
                      *
                    </span>
                  ) : null}
                </span>
                {level ? <LevelBadge level={level} /> : null}
              </label>
            ) : level ? (
              <LevelBadge level={level} />
            ) : (
              <span />
            )}
            {labelAddon}
          </div>
        )}
        {children}
        {error ? (
          <div
            id={describedById}
            role="alert"
            className="text-[11px] text-danger"
          >
            {error}
          </div>
        ) : hint ? (
          <div id={describedById} className="text-[11px] text-muted">
            {hint}
          </div>
        ) : null}
      </div>
    )
  },
)

/** Shared aria attribute helper for inner inputs */
export function describedBy(id: string, hint?: React.ReactNode, error?: React.ReactNode) {
  if (error) return `${id}-error`
  if (hint) return `${id}-hint`
  return undefined
}
