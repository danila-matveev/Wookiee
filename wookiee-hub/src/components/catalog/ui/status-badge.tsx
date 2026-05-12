import { cn } from "@/lib/utils"
import { Badge, type BadgeVariant } from "@/components/ui-v2/primitives"

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

// Maps legacy color names → DS v2 Badge variants
const COLOR_TO_VARIANT: Record<string, BadgeVariant> = {
  green: "success",
  blue:  "info",
  gray:  "default",
  amber: "warning",
  red:   "danger",
}

// CSS-var refs for dot fill — keeps dots in sync with badge tone.
const DOT_VAR: Record<string, string> = {
  green: "bg-[var(--color-success)]",
  blue:  "bg-[var(--color-info)]",
  gray:  "bg-[var(--color-text-muted)]",
  amber: "bg-[var(--color-warning)]",
  red:   "bg-[var(--color-danger)]",
}

function resolveColor(color: StatusColor | null | undefined): string {
  if (!color) return "gray"
  if (color in COLOR_TO_VARIANT) return color
  // unknown colors fall back to gray
  return "gray"
}

interface StatusDotProps {
  color: StatusColor
}

export function StatusDot({ color }: StatusDotProps) {
  const c = resolveColor(color)
  return (
    <span className={cn("inline-block w-1.5 h-1.5 rounded-full shrink-0", DOT_VAR[c])} />
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
 *
 * Под капотом — `<Badge>` из ui-v2 с маппингом цветов:
 *   green→success, blue→info, gray→default, amber→warning, red→danger.
 * Может работать и через `status={...}` (новый API), и через `statusId={...}` (legacy lookup).
 */
export function StatusBadge({
  status, statusId, compact = false, size = "md", className,
}: StatusBadgeProps) {
  const resolved: StatusLike | null = status
    ?? (statusId != null ? CATALOG_STATUSES.find((x) => x.id === statusId) ?? null : null)
  if (!resolved) return null
  const color = resolveColor(resolved.color)
  return (
    <Badge
      variant={COLOR_TO_VARIANT[color]}
      size={size}
      className={cn("rounded-md", className)}
    >
      {!compact && <StatusDot color={color} />}
      {resolved.nazvanie}
    </Badge>
  )
}
