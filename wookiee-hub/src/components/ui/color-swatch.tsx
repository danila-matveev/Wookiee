import { cn } from "@/lib/utils"

export interface ColorSwatchProps {
  color: string
  size?: "sm" | "md" | "lg"
  className?: string
}

const SIZES = { sm: "size-4", md: "size-6", lg: "size-8" }

export function ColorSwatch({ color, size = "md", className }: ColorSwatchProps) {
  return (
    <span
      data-slot="color-swatch"
      className={cn("inline-block rounded-md ring-1 ring-border", SIZES[size], className)}
      style={{ backgroundColor: color }}
    />
  )
}
