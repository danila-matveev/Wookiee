import * as React from "react"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

export type ColorSwatchSize = "sm" | "md" | "lg"

export interface ColorSwatchProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  color: string
  size?: ColorSwatchSize
  selected?: boolean
  label?: string
}

const sizeStyles: Record<ColorSwatchSize, string> = {
  sm: "w-4 h-4",
  md: "w-6 h-6",
  lg: "w-8 h-8",
}

const checkSize: Record<ColorSwatchSize, string> = {
  sm: "w-2.5 h-2.5",
  md: "w-3.5 h-3.5",
  lg: "w-4 h-4",
}

export const ColorSwatch = React.forwardRef<HTMLButtonElement, ColorSwatchProps>(
  function ColorSwatch(
    { color, size = "md", selected = false, label, onClick, className, ...props },
    ref,
  ) {
    const interactive = Boolean(onClick)
    return (
      <button
        ref={ref}
        type="button"
        onClick={onClick}
        aria-label={label ?? `Цвет ${color}`}
        aria-pressed={interactive ? selected : undefined}
        className={cn(
          "relative inline-flex items-center justify-center rounded-full border border-default transition-transform",
          sizeStyles[size],
          interactive && "cursor-pointer hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface)]",
          !interactive && "cursor-default",
          selected && "ring-2 ring-[var(--color-ring)] ring-offset-2 ring-offset-[var(--color-surface)]",
          className,
        )}
        style={{ backgroundColor: color }}
        {...props}
      >
        {selected && (
          <Check className={cn(checkSize[size], "text-white mix-blend-difference")} aria-hidden />
        )}
      </button>
    )
  },
)
