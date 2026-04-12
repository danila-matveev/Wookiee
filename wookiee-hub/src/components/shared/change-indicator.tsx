import { ArrowUpRight, ArrowDownRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface ChangeIndicatorProps {
  value: string
  positive?: boolean
  className?: string
}

export function ChangeIndicator({ value, positive = true, className }: ChangeIndicatorProps) {
  const Icon = positive ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[11px] font-semibold tabular-nums",
        positive
          ? "bg-wk-green/20 text-wk-green"
          : "bg-wk-red/20 text-wk-red",
        className
      )}
    >
      <Icon size={12} />
      {value}
    </span>
  )
}
