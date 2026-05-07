import { Tooltip } from "./tooltip"

type Level = "model" | "variation" | "artikul" | "sku"

const LEVEL_MAP: Record<Level, { label: string; cls: string }> = {
  model:     { label: "модель",   cls: "bg-blue-50   text-blue-700   ring-blue-600/20"   },
  variation: { label: "вариация", cls: "bg-purple-50 text-purple-700 ring-purple-600/20" },
  artikul:   { label: "артикул",  cls: "bg-orange-50 text-orange-700 ring-orange-600/20" },
  sku:       { label: "SKU",      cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
}

interface LevelBadgeProps {
  level: Level
}

export function LevelBadge({ level }: LevelBadgeProps) {
  const m = LEVEL_MAP[level]
  if (!m) return null
  return (
    <Tooltip text={`Поле редактируется на уровне «${m.label}»`}>
      <span
        className={`inline-flex items-center text-[9px] uppercase tracking-wider rounded px-1 py-px ring-1 ring-inset ${m.cls}`}
      >
        {m.label}
      </span>
    </Tooltip>
  )
}
