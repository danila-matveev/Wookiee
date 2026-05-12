import type { ReactNode } from "react"
import { Tooltip as V2Tooltip } from "@/components/ui-v2/primitives"

export type TooltipPosition = "top" | "bottom" | "left" | "right"

interface TooltipProps {
  text: string
  children: ReactNode
  position?: TooltipPosition
  className?: string
}

/**
 * Tooltip — позиционируемая подсказка на hover.
 *
 * Тонкий wrapper над `<Tooltip>` из ui-v2 — сохраняет публичный
 * API каталога (`text`, `children`, `position`) и заворачивает
 * детей в `<span>` чтобы ui-v2 Tooltip получил единственный ReactElement.
 */
export function Tooltip({ text, children, position = "top", className }: TooltipProps) {
  return (
    <V2Tooltip content={text} position={position} className={className}>
      <span className="inline-flex">{children}</span>
    </V2Tooltip>
  )
}
