import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export type TooltipPosition = "top" | "bottom" | "left" | "right"

interface TooltipProps {
  text: string
  children: ReactNode
  position?: TooltipPosition
  className?: string
}

const POSITION_MAP: Record<TooltipPosition, string> = {
  top: "left-1/2 -translate-x-1/2 bottom-full mb-1.5",
  bottom: "left-1/2 -translate-x-1/2 top-full mt-1.5",
  left: "right-full mr-1.5 top-1/2 -translate-y-1/2",
  right: "left-full ml-1.5 top-1/2 -translate-y-1/2",
}

/**
 * Tooltip — позиционируемая подсказка на hover.
 * MVP-spec: stone-900 fill, white text, 11px, fade-in.
 */
export function Tooltip({ text, children, position = "top", className }: TooltipProps) {
  return (
    <span className={cn("group relative inline-flex", className)}>
      {children}
      <span
        className={cn(
          "absolute px-2 py-1 bg-stone-900 text-white text-[11px] rounded whitespace-nowrap",
          "opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50",
          POSITION_MAP[position],
        )}
      >
        {text}
      </span>
    </span>
  )
}
