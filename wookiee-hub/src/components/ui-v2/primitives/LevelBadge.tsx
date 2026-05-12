import * as React from "react"
import { cn } from "@/lib/utils"
import { Badge, type BadgeSize } from "./Badge"

export type PriorityLevel = "P0" | "P1" | "P2" | "P3"

export interface LevelBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  level: PriorityLevel
  size?: BadgeSize
}

const levelToVariant = {
  P0: "danger",
  P1: "warning",
  P2: "info",
  P3: "default",
} as const

export const LevelBadge = React.forwardRef<HTMLSpanElement, LevelBadgeProps>(
  function LevelBadge({ level, size = "sm", className, ...props }, ref) {
    return (
      <Badge
        ref={ref}
        variant={levelToVariant[level]}
        size={size}
        className={cn("font-mono tabular-nums tracking-wider", className)}
        {...props}
      >
        {level}
      </Badge>
    )
  },
)
