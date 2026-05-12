import { cn } from "@/lib/utils"
import { useStatusyMap } from "@/hooks/use-statusy-map"

type StatusColor = "green" | "blue" | "gray" | "amber" | "red" | string

interface Status {
  id: number
  nazvanie: string
  tip: "model" | "product" | "color"
  color: StatusColor
}

// W9.17 — Legacy fixture for tip=model/product. Kept as a last-resort fallback
// when the live `statusy` query has not loaded yet (e.g. very first render of
// references page, or storybook). Production resolves through useStatusyMap().
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

/** Placeholder behaviour when no status is resolvable. */
type Placeholder = "none" | "dash"

interface StatusBadgeProps {
  /** Preferred — pass full status object {nazvanie, color}. Highest priority. */
  status?: StatusLike | null
  /**
   * Status id — resolved live via `useStatusyMap` (the same React Query cache
   * every catalog page populates). Falls back to legacy CATALOG_STATUSES
   * fixture if the query hasn't loaded yet; if still unresolved and `id > 0`,
   * renders a `#N` placeholder so the cell never silently disappears.
   */
  statusId?: number | null
  /** No dot (just pill+text). */
  compact?: boolean
  /** Smaller padding/font (for inline table cells). */
  size?: "sm" | "md"
  /**
   * What to render when nothing is resolvable (status=null and statusId is
   * null/0/undefined). `"none"` returns `null` (back-compat default).
   * `"dash"` returns a muted `—`.
   */
  placeholder?: Placeholder
  className?: string
}

/**
 * StatusBadge — pill + ring + dot, MVP look (`wookiee_matrix_mvp_v4.jsx`).
 *
 * Resolution order (highest priority first):
 *   1. `status` prop — used verbatim.
 *   2. `statusId` → live lookup via `useStatusyMap()` (covers every id from
 *      `statusy`, tip-agnostic).
 *   3. `statusId` → legacy `CATALOG_STATUSES` fixture (ids 1–7) — for the brief
 *      moment before the query loads.
 *   4. `statusId > 0` but still not resolved → muted `#N` placeholder, so
 *      W9.2 status columns never render empty.
 *   5. No id at all → `placeholder` ("none" → `null`, "dash" → muted `—`).
 */
export function StatusBadge({
  status, statusId, compact = false, size = "md", placeholder = "none", className,
}: StatusBadgeProps) {
  // Always call the hook — keeps hook order stable across renders. The query
  // is cached and shared across the whole app, so the cost is one Map lookup.
  const { map: statusyMap } = useStatusyMap()

  let resolved: StatusLike | null = null
  let unknownId: number | null = null

  if (status) {
    resolved = status
  } else if (statusId != null && statusId > 0) {
    const live = statusyMap.get(statusId)
    if (live) {
      resolved = { nazvanie: live.nazvanie, color: live.color }
    } else {
      const legacy = CATALOG_STATUSES.find((x) => x.id === statusId)
      if (legacy) {
        resolved = { nazvanie: legacy.nazvanie, color: legacy.color }
      } else {
        unknownId = statusId
      }
    }
  }

  const sizeCls = size === "sm"
    ? "px-1.5 py-px text-[11px]"
    : "px-2 py-0.5 text-xs"

  if (resolved) {
    const color = resolveColor(resolved.color)
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

  // W9.2/W9.17 — non-empty id that couldn't be resolved → visible `#N` chip.
  if (unknownId != null) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-md ring-1 ring-inset font-mono",
          "bg-stone-100 text-stone-600 ring-stone-500/20",
          sizeCls,
          className,
        )}
      >
        #{unknownId}
      </span>
    )
  }

  // No id, no explicit status.
  if (placeholder === "dash") {
    return (
      <span className={cn("text-[11px] text-stone-400 italic px-1.5 py-px", className)}>—</span>
    )
  }
  return null
}
