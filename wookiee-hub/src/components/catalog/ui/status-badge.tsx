import type { CSSProperties } from "react"

type StatusColor = "green" | "blue" | "gray" | "amber" | "red"

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

const COLOR_MAP: Record<StatusColor, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue:  "bg-blue-50   text-blue-700   ring-blue-600/20",
  gray:  "bg-stone-100 text-stone-600  ring-stone-500/20",
  amber: "bg-amber-50  text-amber-700  ring-amber-600/20",
  red:   "bg-red-50    text-red-700    ring-red-600/20",
}

const DOT_MAP: Record<StatusColor, string> = {
  green: "bg-emerald-500",
  blue:  "bg-blue-500",
  gray:  "bg-stone-400",
  amber: "bg-amber-500",
  red:   "bg-red-500",
}

interface StatusDotProps {
  color: StatusColor
}

export function StatusDot({ color }: StatusDotProps) {
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full ${DOT_MAP[color] ?? "bg-stone-400"}`} />
  )
}

interface StatusBadgeProps {
  statusId: number
  compact?: boolean
}

export function StatusBadge({ statusId, compact = false }: StatusBadgeProps) {
  const s = CATALOG_STATUSES.find((x) => x.id === statusId)
  if (!s) return null
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${COLOR_MAP[s.color]}`}
    >
      {!compact && <StatusDot color={s.color} />}
      {s.nazvanie}
    </span>
  )
}
