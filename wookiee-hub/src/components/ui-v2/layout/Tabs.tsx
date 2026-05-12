import * as React from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export type TabsVariant = "underline" | "pills" | "vertical"

export interface TabItem<V extends string = string> {
  value: V
  label: string
  icon?: LucideIcon
  count?: number
  disabled?: boolean
}

export interface TabsProps<V extends string = string> {
  value: V
  onChange: (value: V) => void
  items: TabItem<V>[]
  variant?: TabsVariant
  className?: string
  /** Optional aria-label for the tablist */
  ariaLabel?: string
}

function CountBadge({ active, value }: { active: boolean; value: number }) {
  return (
    <span
      className={cn(
        "ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1",
        "rounded-full text-[10px] tabular-nums",
        active
          ? "bg-[var(--color-text-primary)] text-[var(--color-surface)]"
          : "bg-surface-muted text-muted border border-default",
      )}
    >
      {value}
    </span>
  )
}

export function Tabs<V extends string = string>({
  value,
  onChange,
  items,
  variant = "underline",
  className,
  ariaLabel,
}: TabsProps<V>) {
  const handleKey = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    idx: number,
  ) => {
    const horizontal = variant !== "vertical"
    const next = horizontal ? "ArrowRight" : "ArrowDown"
    const prev = horizontal ? "ArrowLeft" : "ArrowUp"
    if (e.key !== next && e.key !== prev) return
    e.preventDefault()
    const step = e.key === next ? 1 : -1
    let i = idx
    for (let n = 0; n < items.length; n++) {
      i = (i + step + items.length) % items.length
      if (!items[i].disabled) {
        onChange(items[i].value)
        break
      }
    }
  }

  if (variant === "pills") {
    return (
      <div
        role="tablist"
        aria-label={ariaLabel}
        aria-orientation="horizontal"
        className={cn(
          "inline-flex items-center gap-1 p-0.5 rounded-md bg-surface-muted border border-default",
          className,
        )}
      >
        {items.map((it, idx) => {
          const active = it.value === value
          const Icon = it.icon
          return (
            <button
              key={it.value}
              type="button"
              role="tab"
              aria-selected={active}
              aria-disabled={it.disabled || undefined}
              disabled={it.disabled}
              tabIndex={active ? 0 : -1}
              onClick={() => !it.disabled && onChange(it.value)}
              onKeyDown={(e) => handleKey(e, idx)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 h-7 rounded text-xs font-medium",
                "transition-colors outline-none",
                "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
                active
                  ? "bg-surface text-primary shadow-[var(--shadow-xs)]"
                  : "text-secondary hover:text-primary",
                it.disabled && "opacity-50 cursor-not-allowed",
              )}
            >
              {Icon && <Icon className="w-3.5 h-3.5" aria-hidden />}
              <span>{it.label}</span>
              {typeof it.count === "number" && (
                <CountBadge active={active} value={it.count} />
              )}
            </button>
          )
        })}
      </div>
    )
  }

  if (variant === "vertical") {
    return (
      <div
        role="tablist"
        aria-label={ariaLabel}
        aria-orientation="vertical"
        className={cn("flex flex-col gap-0.5", className)}
      >
        {items.map((it, idx) => {
          const active = it.value === value
          const Icon = it.icon
          return (
            <button
              key={it.value}
              type="button"
              role="tab"
              aria-selected={active}
              aria-disabled={it.disabled || undefined}
              disabled={it.disabled}
              tabIndex={active ? 0 : -1}
              onClick={() => !it.disabled && onChange(it.value)}
              onKeyDown={(e) => handleKey(e, idx)}
              className={cn(
                "group w-full flex items-center gap-2.5 px-3 h-8 rounded-md text-sm text-left",
                "transition-colors outline-none",
                "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
                active
                  ? "bg-surface-muted text-primary font-medium"
                  : "text-secondary hover:bg-surface-muted hover:text-primary",
                it.disabled && "opacity-50 cursor-not-allowed",
              )}
            >
              {Icon && (
                <Icon
                  className={cn(
                    "w-3.5 h-3.5 shrink-0",
                    active ? "text-primary" : "text-muted",
                  )}
                  aria-hidden
                />
              )}
              <span className="flex-1 truncate">{it.label}</span>
              {typeof it.count === "number" && (
                <CountBadge active={active} value={it.count} />
              )}
            </button>
          )
        })}
      </div>
    )
  }

  // underline (default)
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      aria-orientation="horizontal"
      className={cn(
        "flex items-center gap-1 border-b border-default",
        className,
      )}
    >
      {items.map((it, idx) => {
        const active = it.value === value
        const Icon = it.icon
        return (
          <button
            key={it.value}
            type="button"
            role="tab"
            aria-selected={active}
            aria-disabled={it.disabled || undefined}
            disabled={it.disabled}
            tabIndex={active ? 0 : -1}
            onClick={() => !it.disabled && onChange(it.value)}
            onKeyDown={(e) => handleKey(e, idx)}
            className={cn(
              "relative inline-flex items-center gap-1.5 px-3 py-2 -mb-px text-sm",
              "border-b-2 transition-colors outline-none",
              "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
              active
                ? "border-[var(--color-text-primary)] text-primary font-medium"
                : "border-transparent text-secondary hover:text-primary",
              it.disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            {Icon && <Icon className="w-3.5 h-3.5" aria-hidden />}
            <span>{it.label}</span>
            {typeof it.count === "number" && (
              <CountBadge active={active} value={it.count} />
            )}
          </button>
        )
      })}
    </div>
  )
}
