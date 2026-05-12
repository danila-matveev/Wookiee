import * as React from "react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError } from "./_shared"
import type { CatalogLevel } from "../primitives"

export interface TextareaFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  /** Catalog-hierarchy marker rendered inline with the label (M/V/A/S). */
  level?: CatalogLevel
  labelAddon?: React.ReactNode

  value: string
  onChange: (next: string) => void
  placeholder?: string
  disabled?: boolean
  readOnly?: boolean
  autoFocus?: boolean
  rows?: number
  maxLength?: number
  /** Auto-resize textarea height to fit content (caps roughly at 12rem).
   * Opt-in — canonical default (foundation.jsx:535-544) is fixed rows + resize-none. */
  autoResize?: boolean
  name?: string

  className?: string
  inputClassName?: string

  onBlur?: React.FocusEventHandler<HTMLTextAreaElement>
  onFocus?: React.FocusEventHandler<HTMLTextAreaElement>
}

export const TextareaField = React.forwardRef<HTMLTextAreaElement, TextareaFieldProps>(
  function TextareaField(
    {
      id,
      label,
      hint,
      error,
      required,
      level,
      labelAddon,
      value,
      onChange,
      placeholder,
      disabled,
      readOnly,
      autoFocus,
      rows = 3,
      maxLength,
      autoResize = false,
      name,
      className,
      inputClassName,
      onBlur,
      onFocus,
    },
    ref,
  ) {
    const aria = describedBy(id, hint, error)
    const innerRef = React.useRef<HTMLTextAreaElement | null>(null)

    const setRefs = (node: HTMLTextAreaElement | null) => {
      innerRef.current = node
      if (typeof ref === "function") ref(node)
      else if (ref) {
        ;(ref as React.MutableRefObject<HTMLTextAreaElement | null>).current = node
      }
    }

    React.useEffect(() => {
      if (!autoResize) return
      const el = innerRef.current
      if (!el) return
      el.style.height = "auto"
      el.style.height = `${Math.min(el.scrollHeight, 192)}px`
    }, [value, autoResize])

    // Render counter only when caller opts in via maxLength AND user is
    // approaching the limit. Saves layout cost on every field.
    const showCounter =
      typeof maxLength === "number" && value.length > maxLength * 0.7

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
        <textarea
          ref={setRefs}
          id={id}
          name={name}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          readOnly={readOnly}
          required={required}
          autoFocus={autoFocus}
          maxLength={maxLength}
          aria-invalid={error ? true : undefined}
          aria-describedby={aria}
          onBlur={onBlur}
          onFocus={onFocus}
          className={cn(
            inputBase,
            "px-2.5 py-1.5",
            autoResize ? "resize-none overflow-hidden" : "resize-none",
            error && inputError,
            inputClassName,
          )}
        />
        {showCounter ? (
          <div className="text-[10px] text-muted text-right tabular-nums mt-1">
            {value.length}/{maxLength}
          </div>
        ) : null}
      </FieldWrap>
    )
  },
)
