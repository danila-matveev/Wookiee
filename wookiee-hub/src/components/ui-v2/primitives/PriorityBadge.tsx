import * as React from "react"
import { Badge, type BadgeVariant, type BadgeSize } from "./Badge"

// Task priority levels — extension on top of canonical Badge. Was previously
// shipped as `LevelBadge`, renamed here so the canonical catalog-hierarchy
// `LevelBadge` (M/V/A/S) can take that name back.
export type PriorityLevel = "P0" | "P1" | "P2" | "P3"

export interface PriorityBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  level: PriorityLevel
  size?: BadgeSize
}

const levelToVariant: Record<PriorityLevel, BadgeVariant> = {
  P0: "danger",
  P1: "warning",
  P2: "info",
  P3: "default",
}

export const PriorityBadge = React.forwardRef<HTMLSpanElement, PriorityBadgeProps>(
  function PriorityBadge({ level, size = "sm", className, ...props }, ref) {
    return (
      <Badge
        ref={ref}
        variant={levelToVariant[level]}
        size={size}
        className={["font-mono tabular-nums tracking-wider", className]
          .filter(Boolean)
          .join(" ")}
        {...props}
      >
        {level}
      </Badge>
    )
  },
)
