import { Badge, type BadgeVariant } from "@/components/ui-v2/primitives"
import { Tooltip } from "./tooltip"

export type Level = "model" | "variation" | "artikul" | "sku"

const LEVEL_MAP: Record<Level, { label: string; variant: BadgeVariant }> = {
  model:     { label: "модель",   variant: "info"    },
  variation: { label: "вариация", variant: "accent"  },
  artikul:   { label: "артикул",  variant: "warning" },
  sku:       { label: "SKU",      variant: "success" },
}

interface LevelBadgeProps {
  level: Level
}

/**
 * LevelBadge — отметка уровня поля (модель / вариация / артикул / SKU).
 *
 * Использует `<Badge>` из ui-v2 с маппингом на semantic variants:
 * - model     → info     (синий)
 * - variation → accent   (фиолетовый бренд)
 * - artikul   → warning  (оранжевый)
 * - sku       → success  (зелёный)
 */
export function LevelBadge({ level }: LevelBadgeProps) {
  const m = LEVEL_MAP[level]
  if (!m) return null
  return (
    <Tooltip text={`Поле редактируется на уровне «${m.label}»`}>
      <Badge
        variant={m.variant}
        size="sm"
        className="uppercase tracking-wider text-[9px]"
      >
        {m.label}
      </Badge>
    </Tooltip>
  )
}
