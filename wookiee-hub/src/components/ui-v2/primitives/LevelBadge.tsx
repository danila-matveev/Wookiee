import * as React from "react"
import { Badge, type BadgeColor } from "./Badge"

// Canonical: catalog hierarchy markers M / V / A / S — foundation.jsx:308-315.
export type CatalogLevel = "model" | "variation" | "artikul" | "sku"

const LEVEL_MAP: Record<CatalogLevel, { letter: string; color: BadgeColor }> = {
  model: { letter: "M", color: "blue" },
  variation: { letter: "V", color: "purple" },
  artikul: { letter: "A", color: "orange" },
  sku: { letter: "S", color: "emerald" },
}

export interface LevelBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  level: CatalogLevel
}

/**
 * LevelBadge — canonical catalog-hierarchy marker.
 *
 * `<LevelBadge level="model" />` → blue "M" pill. Used inside FieldWrap to
 * indicate which level a field is editable at.
 *
 * For task-priority badges (P0..P3) see `PriorityBadge`.
 */
export const LevelBadge = React.forwardRef<HTMLSpanElement, LevelBadgeProps>(
  function LevelBadge({ level, className, ...props }, ref) {
    const entry = LEVEL_MAP[level]
    if (!entry) return null
    return (
      <Badge
        ref={ref}
        variant={entry.color}
        compact
        className={className}
        {...props}
      >
        {entry.letter}
      </Badge>
    )
  },
)
