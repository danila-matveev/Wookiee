import { Tooltip } from "./tooltip"
import { LevelBadge as V2LevelBadge, type CatalogLevel } from "@/components/ui-v2/primitives"

// Catalog uses the same canonical level vocabulary as ui-v2.
export type Level = CatalogLevel

const LEVEL_LABEL: Record<Level, string> = {
  model: "модель",
  variation: "вариация",
  artikul: "артикул",
  sku: "SKU",
}

interface LevelBadgeProps {
  level: Level
}

/**
 * LevelBadge — catalog-flavoured wrapper over canonical ui-v2 LevelBadge.
 *
 * Canonical badge shows a single letter (M/V/A/S) in the brand-mandated color.
 * The catalog adapter additionally wraps the badge in a Tooltip explaining
 * which level the field is editable at.
 */
export function LevelBadge({ level }: LevelBadgeProps) {
  const label = LEVEL_LABEL[level]
  if (!label) return null
  return (
    <Tooltip text={`Поле редактируется на уровне «${label}»`}>
      <V2LevelBadge level={level} />
    </Tooltip>
  )
}
