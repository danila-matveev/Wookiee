import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { BadgeVariant, BadgeSize } from "./Badge"

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  icon?: React.ComponentType<{ className?: string }>
  onRemove?: () => void
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-surface-muted text-secondary border-default",
  accent: "bg-accent-soft text-accent border-accent",
  success: "bg-success-soft text-success border-default",
  warning: "bg-warning-soft text-warning border-default",
  danger: "bg-danger-soft text-danger border-default",
  info: "bg-info-soft text-info border-default",
}

const sizeStyles: Record<BadgeSize, string> = {
  sm: "h-5 px-1.5 text-[11px] gap-1 rounded",
  md: "h-6 px-2 text-xs gap-1.5 rounded-md",
}

const iconSize: Record<BadgeSize, string> = {
  sm: "w-2.5 h-2.5",
  md: "w-3 h-3",
}

export const Tag = React.forwardRef<HTMLSpanElement, TagProps>(function Tag(
  { variant = "default", size = "md", icon: Icon, onRemove, className, children, ...props },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center font-medium border",
        sizeStyles[size],
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {Icon && <Icon className={iconSize[size]} aria-hidden />}
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          aria-label="Удалить"
          className="ml-0.5 inline-flex items-center justify-center rounded p-0.5 hover:bg-surface-muted/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-ring)]"
        >
          <X className={iconSize[size]} aria-hidden />
        </button>
      )}
    </span>
  )
})
