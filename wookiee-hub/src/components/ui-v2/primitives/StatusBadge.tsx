import * as React from "react"
import { cn } from "@/lib/utils"
import { Badge, type BadgeSize } from "./Badge"

export type StatusTone = "success" | "warning" | "danger" | "info" | "muted"

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: StatusTone
  size?: BadgeSize
}

const dotColor: Record<StatusTone, string> = {
  success: "bg-[var(--color-success)]",
  warning: "bg-[var(--color-warning)]",
  danger: "bg-[var(--color-danger)]",
  info: "bg-[var(--color-info)]",
  muted: "bg-[var(--color-text-muted)]",
}

const toneToBadgeVariant = {
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
  muted: "default",
} as const

export const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  function StatusBadge({ tone = "muted", size = "md", className, children, ...props }, ref) {
    return (
      <Badge
        ref={ref}
        variant={toneToBadgeVariant[tone]}
        size={size}
        className={cn(className)}
        {...props}
      >
        <span
          aria-hidden
          className={cn(
            "inline-block rounded-full shrink-0",
            size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2",
            dotColor[tone],
          )}
        />
        {children}
      </Badge>
    )
  },
)
