import { cn } from "@/lib/utils"

interface ProgressBarProps {
  value: number
  className?: string
}

export function ProgressBar({ value, className }: ProgressBarProps) {
  return (
    <div className={cn("h-1 rounded-full bg-bg-hover overflow-hidden", className)}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-wk-green to-accent transition-[width] duration-300"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}
