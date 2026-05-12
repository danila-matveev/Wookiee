import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface ChipProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, "onClick"> {
  onRemove?: () => void
  icon?: React.ComponentType<{ className?: string }>
}

/**
 * Chip — canonical removable token (foundation.jsx:317).
 *
 * Passive `<span>` with optional `onRemove` X button. For selectable
 * filter pills see `FilterChip`.
 */
export const Chip = React.forwardRef<HTMLSpanElement, ChipProps>(function Chip(
  { onRemove, icon: Icon, className, children, ...props },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs",
        "bg-surface-muted text-secondary",
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="w-3 h-3" aria-hidden />}
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Удалить"
          className="ml-0.5 inline-flex items-center justify-center rounded p-0.5 hover:bg-current/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-ring)]"
        >
          <X className="w-3 h-3" aria-hidden />
        </button>
      )}
    </span>
  )
})
