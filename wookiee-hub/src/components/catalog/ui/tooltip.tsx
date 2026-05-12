import type { ReactNode } from "react"
import * as RTooltip from "@radix-ui/react-tooltip"
import { cn } from "@/lib/utils"

export type TooltipPosition = "top" | "bottom" | "left" | "right"

interface TooltipProps {
  text: string
  children: ReactNode
  position?: TooltipPosition
  className?: string
}

/**
 * Tooltip — позиционируемая подсказка на hover/focus.
 * Реализована на Radix Tooltip с collisionPadding={8}, чтобы не обрезаться
 * за сайдбаром/краем вьюпорта. Сохраняет прежний API (text, children, position, className).
 * MVP-spec: stone-900 fill, white text, 11px, fade-in.
 */
export function Tooltip({ text, children, position = "top", className }: TooltipProps) {
  return (
    <RTooltip.Provider delayDuration={150} skipDelayDuration={100}>
      <RTooltip.Root>
        <RTooltip.Trigger asChild>
          <span className={cn("inline-flex", className)}>{children}</span>
        </RTooltip.Trigger>
        <RTooltip.Portal>
          <RTooltip.Content
            side={position}
            align="center"
            sideOffset={6}
            collisionPadding={8}
            avoidCollisions
            className={cn(
              "z-50 px-2 py-1 bg-stone-900 text-white text-[11px] rounded",
              "max-w-xs whitespace-normal break-words",
              "data-[state=delayed-open]:animate-in data-[state=closed]:animate-out",
              "data-[state=delayed-open]:fade-in-0 data-[state=closed]:fade-out-0",
            )}
          >
            {text}
          </RTooltip.Content>
        </RTooltip.Portal>
      </RTooltip.Root>
    </RTooltip.Provider>
  )
}
