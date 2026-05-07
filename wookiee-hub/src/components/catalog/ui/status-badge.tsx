import { cn } from "@/lib/utils"

type StatusColor = "green" | "blue" | "gray" | "amber" | "red" | string

interface Status {
  id: number
  nazvanie: string
  tip: "model" | "product" | "color"
  color: StatusColor
}

// Client-side status lookup — matches Supabase statusy table
export const CATALOG_STATUSES: Status[] = [
  { id: 1, nazvanie: "В продаже",  tip: "model",   color: "green" },
  { id: 2, nazvanie: "Запуск",     tip: "model",   color: "blue"  },
  { id: 3, nazvanie: "Архив",      tip: "model",   color: "gray"  },
  { id: 4, nazvanie: "Разработка", tip: "model",   color: "amber" },
  { id: 5, nazvanie: "Выводим",    tip: "product", color: "red"   },
  { id: 6, nazvanie: "Продаётся",  tip: "product", color: "green" },
  { id: 7, nazvanie: "Скрыт",      tip: "product", color: "gray"  },
]

const COLOR_MAP: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue:  "bg-blue-50   text-blue-700   ring-blue-600/20",
  gray:  "bg-stone-100 text-stone-600  ring-stone-500/20",
  amber: "bg-amber-50  text-amber-700  ring-amber-600/20",
  red:   "bg-red-50    text-red-700    ring-red-600/20",
}

const DOT_MAP: Record<string, string> = {
  green: "bg-emerald-500",
  blue:  "bg-blue-500",
  gray:  "bg-stone-400",
  amber: "bg-amber-500",
  red:   "bg-red-500",
}

function resolveColor(color: StatusColor | null | undefined): string {
  if (!color) return "gray"
  if (color in COLOR_MAP) return color
  // unknown colors fall back to gray
  return "gray"
}

interface StatusDotProps {
  color: StatusColor
}

export function StatusDot({ color }: StatusDotProps) {
  const c = resolveColor(color)
  return (
    <span className={cn("inline-block w-1.5 h-1.5 rounded-full shrink-0", DOT_MAP[c])} />
  )
}

// MVP-spec interface: status: { nazvanie, color }
interface StatusLike {
  nazvanie: string
  color?: StatusColor | null
}

interface StatusBadgeProps {
  /** Preferred — pass full status object {nazvanie, color}. */
  status?: StatusLike | null
  /** Legacy — lookup by id in CATALOG_STATUSES. */
  statusId?: number
  /** No dot (just pill+text). */
  compact?: boolean
  /** Smaller padding/font (for inline table cells). */
  size?: "sm" | "md"
  className?: string
}

/**
 * StatusBadge — pill + ring + dot, как в MVP wookiee_matrix_mvp_v4.jsx.
 * Может работать и через `status={...}` (новый API), и через `statusId={...}` (legacy lookup).
 */
export function StatusBadge({
  status, statusId, compact = false, size = "md", className,
}: StatusBadgeProps) {
  const resolved: StatusLike | null = status
    ?? (statusId != null ? CATALOG_STATUSES.find((x) => x.id === statusId) ?? null : null)
  if (!resolved) return null
  const color = resolveColor(resolved.color)
  const sizeCls = size === "sm"
    ? "px-1.5 py-px text-[11px]"
    : "px-2 py-0.5 text-xs"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md font-medium ring-1 ring-inset",
        sizeCls,
        COLOR_MAP[color],
        className,
      )}
    >
      {!compact && <StatusDot color={color} />}
      {resolved.nazvanie}
    </span>
  )
}
