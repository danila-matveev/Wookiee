import * as React from "react"
import { cn } from "@/lib/utils"

export interface CheckboxProps {
  /** Controlled checked state. */
  checked: boolean
  /** Change callback — receives the next boolean state. */
  onChange: (next: boolean) => void
  /** Optional inline label rendered to the right. */
  label?: React.ReactNode
  /** Render the input in indeterminate state (visual dash). */
  indeterminate?: boolean
  /** Native id — wires up <label htmlFor>. */
  id?: string
  /** Native form name. */
  name?: string
  /** Disable interaction + dim the row. */
  disabled?: boolean
  /** Optional className on the outer wrapper. */
  className?: string
}

/**
 * Checkbox — canonical DS v2 atom (foundation.jsx:235-245).
 *
 * Shape: 14×14 native checkbox with `accent-[var(--color-text-primary)]`
 * so the filled state follows the primary token (stone-900 light, stone-50 dark).
 * Wrapped in a `<label>` when `label` prop is supplied.
 */
export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  function Checkbox(
    { checked, onChange, label, indeterminate, id, name, disabled, className },
    forwardedRef,
  ) {
    const innerRef = React.useRef<HTMLInputElement | null>(null)
    React.useImperativeHandle(forwardedRef, () => innerRef.current as HTMLInputElement)
    React.useEffect(() => {
      if (innerRef.current) innerRef.current.indeterminate = !!indeterminate
    }, [indeterminate])

    const input = (
      <input
        ref={innerRef}
        id={id}
        name={name}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="w-3.5 h-3.5 rounded accent-[var(--color-text-primary)] cursor-pointer disabled:cursor-not-allowed"
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
