import * as React from "react"
import { Badge, type BadgeColor, type BadgeVariant, type BadgeSize } from "./Badge"

// Canonical STATUS_MAP — foundation.jsx:148-154.
export type StatusId = 1 | 2 | 3 | 4 | 5

export const STATUS_MAP: Record<StatusId, { label: string; color: BadgeColor }> = {
  1: { label: "В продаже", color: "emerald" },
  2: { label: "Запуск", color: "blue" },
  3: { label: "Выводим", color: "amber" },
  4: { label: "Не выводится", color: "red" },
  5: { label: "Архив", color: "gray" },
}

// Legacy tone API — kept as a thin alias for backwards compatibility.
export type StatusTone = "success" | "warning" | "danger" | "info" | "muted"

const toneToVariant: Record<StatusTone, BadgeVariant> = {
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
  muted: "default",
}

type StatusBadgePropsById = {
  statusId: StatusId | number
  dot?: boolean
  compact?: boolean
  className?: string
  size?: BadgeSize
}

type StatusBadgePropsByTone = {
  /** @deprecated Use `statusId` and rely on STATUS_MAP. */
  tone: StatusTone
  children: React.ReactNode
  size?: BadgeSize
  className?: string
}

export type StatusBadgeProps = StatusBadgePropsById | StatusBadgePropsByTone

function isToneProps(props: StatusBadgeProps): props is StatusBadgePropsByTone {
  return "tone" in props
}

/**
 * StatusBadge — canonical: `statusId={1..5}` resolves through STATUS_MAP.
 *
 * Overload (deprecated): `tone="success" | ...`+`children` renders a thin
 * Badge alias. Kept so legacy consumers in this repo keep compiling while
 * we migrate to the canonical API.
 */
export const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  function StatusBadge(props, ref) {
    if (isToneProps(props)) {
      const { tone, children, size = "md", className } = props
      return (
        <Badge
          ref={ref}
          variant={toneToVariant[tone]}
          size={size}
          className={className}
        >
          {children}
        </Badge>
      )
    }
    const { statusId, dot = true, compact = true, className, size } = props
    const entry = STATUS_MAP[statusId as StatusId]
    if (!entry) return null
    return (
      <Badge
        ref={ref}
        variant={entry.color}
        size={size}
        compact={compact}
        dot={dot}
        className={className}
      >
        {entry.label}
      </Badge>
    )
  },
)
