import * as React from "react"
import { cn } from "@/lib/utils"

export interface FilterChipProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  selected?: boolean
  icon?: React.ComponentType<{ className?: string }>
}

/**
 * FilterChip — selectable toggle pill. Extension on top of the canonical
 * Tabs `pill` variant for cases where you need a standalone togglable filter
 * (e.g. Notifications panel filter row).
 *
 * For removable tokens see `Chip`.
 */
export const FilterChip = React.forwardRef<HTMLButtonElement, FilterChipProps>(
  function FilterChip(
    { selected = false, icon: Icon, className, children, disabled, ...props },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type="button"
        aria-pressed={selected}
        disabled={disabled}
        className={cn(
          "inline-flex items-center gap-1.5 h-7 px-3 text-xs font-medium rounded-md transition-colors outline-none",
          "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface)]",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          selected
            ? "bg-[var(--color-text-primary)] text-[var(--color-surface)]"
            : "border border-default text-secondary bg-surface hover:bg-surface-muted",
          className,
        )}
        {...props}
      >
        {Icon && <Icon className="w-3 h-3" aria-hidden />}
        {children}
      </button>
    )
  },
)
