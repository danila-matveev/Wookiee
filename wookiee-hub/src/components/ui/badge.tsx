import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type Variant = "emerald" | "blue" | "amber" | "red" | "purple" | "teal" | "gray"
type Size = "xs" | "sm"

const VARIANTS: Record<Variant, string> = {
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-900",
  blue:    "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:ring-blue-900",
  amber:   "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900",
  red:     "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-300 dark:ring-red-900",
  purple:  "bg-purple-50 text-purple-700 ring-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:ring-purple-900",
  teal:    "bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950 dark:text-teal-300 dark:ring-teal-900",
  gray:    "bg-stone-100 text-stone-700 ring-stone-200 dark:bg-stone-900 dark:text-stone-300 dark:ring-stone-800",
}

const SIZES: Record<Size, string> = {
  xs: "text-[10px] px-1.5 py-0.5",
  sm: "text-xs px-2 py-0.5",
}

export interface BadgeProps {
  variant?: Variant
  size?: Size
  dot?: boolean
  icon?: ReactNode
  children: ReactNode
  className?: string
}

export function Badge({
  variant = "emerald",
  size = "sm",
  dot,
  icon,
  children,
  className,
}: BadgeProps) {
  return (
    <span
      data-slot="badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-full ring-1 ring-inset font-medium",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    >
      {dot && <span data-slot="badge-dot" className="size-1.5 rounded-full bg-current" />}
      {icon && <span data-slot="badge-icon">{icon}</span>}
      {children}
    </span>
  )
}
