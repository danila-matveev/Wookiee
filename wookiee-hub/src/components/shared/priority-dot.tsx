import { cn } from "@/lib/utils"

interface PriorityDotProps {
  priority: "high" | "medium" | "low"
  size?: number
  className?: string
}

const colorMap: Record<PriorityDotProps["priority"], string> = {
  high: "bg-wk-red",
  medium: "bg-wk-yellow",
  low: "bg-text-dim",
}

export function PriorityDot({ priority, size = 6, className }: PriorityDotProps) {
  return (
    <span
      className={cn("inline-block rounded-full shrink-0", colorMap[priority], className)}
      style={{ width: size, height: size }}
    />
  )
}
