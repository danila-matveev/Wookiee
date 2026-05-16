import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type Level = "model" | "variation" | "artikul" | "sku"

const LEVELS: Record<Level, string> = {
  model:     "bg-purple-50 text-purple-700 ring-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:ring-purple-900",
  variation: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:ring-blue-900",
  artikul:   "bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950 dark:text-teal-300 dark:ring-teal-900",
  sku:       "bg-stone-100 text-stone-700 ring-stone-200 dark:bg-stone-900 dark:text-stone-300 dark:ring-stone-800",
}

export interface LevelBadgeProps {
  level: Level
  children: ReactNode
  className?: string
}

export function LevelBadge({ level, children, className }: LevelBadgeProps) {
  return (
    <span
      data-slot="level-badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-md ring-1 ring-inset px-1.5 py-0.5 text-xs font-mono font-medium",
        LEVELS[level],
        className,
      )}
    >
      {children}
    </span>
  )
}
