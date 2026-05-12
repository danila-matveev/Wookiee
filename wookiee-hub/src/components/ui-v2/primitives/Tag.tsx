import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

// Canonical Tag is smaller than Badge — see foundation.jsx:446.
// We keep the full color palette so any team-coloured tag works.
export type TagColor =
  | "gray"
  | "blue"
  | "emerald"
  | "amber"
  | "red"
  | "purple"
  | "orange"
  | "teal"

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  color?: TagColor
  icon?: React.ComponentType<{ className?: string }>
  onRemove?: () => void
}

// text-{c}-700 dark:text-{c}-300 + bg-{c}-50 dark:bg-{c}-950/40.
// gray uses stone scale (canonical line 451).
const colorStyles: Record<TagColor, string> = {
  gray: "bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300",
  blue: "bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300",
  emerald: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300",
  amber: "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300",
  red: "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300",
  purple: "bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300",
  orange: "bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300",
  teal: "bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-300",
}

export const Tag = React.forwardRef<HTMLSpanElement, TagProps>(function Tag(
  { color = "gray", icon: Icon, onRemove, className, children, ...props },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] rounded font-medium ring-1 ring-inset ring-transparent",
        colorStyles[color],
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="w-2.5 h-2.5" aria-hidden />}
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          aria-label="Удалить"
          className="ml-0.5 inline-flex items-center justify-center rounded p-0.5 hover:bg-current/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-ring)]"
        >
          <X className="w-2.5 h-2.5" aria-hidden />
        </button>
      )}
    </span>
  )
})
