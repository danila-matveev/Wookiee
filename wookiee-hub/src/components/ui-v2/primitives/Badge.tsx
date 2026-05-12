import * as React from "react"
import { cn } from "@/lib/utils"

// Canonical Badge color names plus semantic aliases. Color names map 1:1 to
// foundation.jsx:281-300 recipe. Semantic aliases (success/warning/danger/info/
// accent + legacy `default`) resolve to their canonical color twin.
export type BadgeColor =
  | "gray"
  | "emerald"
  | "blue"
  | "amber"
  | "red"
  | "rose"
  | "purple"
  | "orange"
  | "teal"
  | "indigo"

export type BadgeVariant =
  | BadgeColor
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "accent"

export type BadgeSize = "sm" | "md"

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  /** Alias for `compact` (true == canonical compact). Defaults to size='md'. */
  compact?: boolean
  icon?: React.ComponentType<{ className?: string }>
  dot?: boolean
}

// Resolve semantic aliases to a canonical color.
const aliasToColor: Record<Exclude<BadgeVariant, BadgeColor>, BadgeColor> = {
  default: "gray",
  success: "emerald",
  warning: "amber",
  danger: "rose",
  info: "blue",
  accent: "purple",
}

// Per-color recipe — bg-{c}-50 dark:bg-{c}-950/40 text-{c}-700 dark:text-{c}-300
// ring-{c}-600/20 dark:ring-{c}-500/30. gray uses stone scale (canonical).
const colorStyles: Record<BadgeColor, string> = {
  gray:
    "bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 ring-stone-500/20 dark:ring-stone-600/40",
  emerald:
    "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 ring-emerald-600/20 dark:ring-emerald-500/30",
  blue:
    "bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 ring-blue-600/20 dark:ring-blue-500/30",
  amber:
    "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 ring-amber-600/20 dark:ring-amber-500/30",
  red:
    "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 ring-red-600/20 dark:ring-red-500/30",
  rose:
    "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 ring-rose-600/20 dark:ring-rose-500/30",
  purple:
    "bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 ring-purple-600/20 dark:ring-purple-500/30",
  orange:
    "bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300 ring-orange-600/20 dark:ring-orange-500/30",
  teal:
    "bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-300 ring-teal-600/20 dark:ring-teal-500/30",
  indigo:
    "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 ring-indigo-600/20 dark:ring-indigo-500/30",
}

function resolveColor(variant: BadgeVariant): BadgeColor {
  if (variant in aliasToColor) {
    return aliasToColor[variant as keyof typeof aliasToColor]
  }
  return variant as BadgeColor
}

const iconSize = "w-3 h-3"

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  function Badge(
    {
      variant = "default",
      size = "md",
      compact,
      icon: Icon,
      dot,
      className,
      children,
      ...props
    },
    ref,
  ) {
    const color = resolveColor(variant)
    const isCompact = compact ?? size === "sm"
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md font-medium ring-1 ring-inset",
          isCompact ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs",
          colorStyles[color],
          className,
        )}
        {...props}
      >
        {dot && (
          <span
            aria-hidden
            className="inline-block w-1.5 h-1.5 rounded-full bg-current shrink-0"
          />
        )}
        {Icon && <Icon className={iconSize} aria-hidden />}
        {children}
      </span>
    )
  },
)
