import type { ReactNode } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface BulkAction {
  id: string
  label: string
  icon?: ReactNode
  onClick: () => void
  /** Visually marks destructive actions (red text). */
  destructive?: boolean
  /** Disable button (e.g. when constraints not met). */
  disabled?: boolean
}

interface BulkActionsBarProps {
  selectedCount: number
  actions: BulkAction[]
  onClear: () => void
  className?: string
  /** Position: 'sticky-bottom' is the MVP default — pinned to bottom of parent flex container. */
  position?: "sticky-bottom" | "fixed-bottom"
}

/**
 * BulkActionsBar — фиксированный нижний бар, появляется при selectedCount > 0.
 * MVP-spec: «Выбрано: N | actions… | Очистить».
 */
export function BulkActionsBar({
  selectedCount, actions, onClear, className, position = "sticky-bottom",
}: BulkActionsBarProps) {
  if (selectedCount <= 0) return null

  const positionCls = position === "fixed-bottom"
    ? "fixed bottom-0 left-0 right-0 z-40"
    : ""

  return (
    <div
      className={cn(
        "border-t border-default bg-surface px-6 py-3 flex items-center gap-3 shrink-0",
        "shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.08)]",
        positionCls,
        className,
      )}
    >
      <span className="text-sm text-primary">
        Выбрано: <span className="font-medium tabular-nums">{selectedCount}</span>
      </span>
      <div className="h-5 w-px bg-[var(--color-border-default)]" />
      {actions.map((a) => (
        <button
          key={a.id}
          type="button"
          onClick={a.onClick}
          disabled={a.disabled}
          className={cn(
            "px-3 py-1 text-xs rounded-md flex items-center gap-1.5",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            a.destructive
              ? "text-danger hover:bg-danger-soft"
              : "text-secondary hover:bg-surface-muted",
          )}
        >
          {a.icon}
          {a.label}
        </button>
      ))}
      <button
        type="button"
        onClick={onClear}
        className="ml-auto px-3 py-1 text-xs text-muted hover:bg-surface-muted rounded-md flex items-center gap-1.5"
      >
        <X className="w-3 h-3" /> Очистить
      </button>
    </div>
  )
}
