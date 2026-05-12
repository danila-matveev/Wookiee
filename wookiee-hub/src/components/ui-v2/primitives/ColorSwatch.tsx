import * as React from "react"
import { cn } from "@/lib/utils"

export interface ColorSwatchProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> {
  /** CSS color (hex / rgb / var(--…) / etc.). */
  hex: string
  /** Edge length in px. Default 16 (canonical). */
  size?: number
  /** If true, render the hex string as a monospace label after the swatch. */
  label?: boolean
}

/**
 * ColorSwatch — passive token-display per canonical (foundation.jsx:373).
 *
 * `<ColorSwatch hex="#1C1917" size={20} label />` renders a 20px coloured
 * square + the hex code in mono. For interactive color pickers, see future
 * `ColorPicker` primitive (R3).
 */
export const ColorSwatch = React.forwardRef<HTMLSpanElement, ColorSwatchProps>(
  function ColorSwatch({ hex, size = 16, label = false, className, ...props }, ref) {
    return (
      <span
        ref={ref}
        className={cn("inline-flex items-center gap-1.5", className)}
        {...props}
      >
        <span
          aria-hidden
          className="inline-block rounded ring-1 ring-[var(--color-border-default)] shrink-0"
          style={{ width: size, height: size, background: hex }}
        />
        {label && (
          <span className="text-[10px] font-mono text-muted">{hex}</span>
        )}
      </span>
    )
  },
)
