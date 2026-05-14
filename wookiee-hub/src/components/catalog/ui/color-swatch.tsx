import { colorSwatchStyle } from "@/lib/catalog/color-utils"

interface ColorSwatchProps {
  /** hex из БД (`cveta.hex`). null/пусто/невалидно → серая штриховка-плейсхолдер. */
  hex: string | null | undefined
  size?: number
  /** Дополнительный className для swatch'а. */
  className?: string
  /** shape по умолчанию `rect`. У больших swatch'ей (40+) выглядит лучше как `circle`. */
  shape?: "rect" | "circle"
}

/**
 * Единый swatch цвета. Использует `colorSwatchStyle` для нормализации hex
 * и честного placeholder при отсутствии значения.
 */
export function ColorSwatch({ hex, size = 16, className = "", shape = "rect" }: ColorSwatchProps) {
  const radiusClass = shape === "circle" ? "rounded-full" : "rounded"
  return (
    <span
      className={`inline-block ${radiusClass} ring-1 ring-stone-200 shrink-0 ${className}`}
      style={{ ...colorSwatchStyle(hex), width: size, height: size }}
    />
  )
}
