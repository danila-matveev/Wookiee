import * as React from "react"
import { cn } from "@/lib/utils"

export type BadgeVariant =
  | "default"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "info"
export type BadgeSize = "sm" | "md"

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  icon?: React.ComponentType<{ className?: string }>
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

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  function Badge(
    { variant = "default", size = "md", icon: Icon, className, children, ...props },
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
      </span>
    )
  },
)
