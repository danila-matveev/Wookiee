import { cn } from "@/lib/utils"
import type { RunStatus } from "@/types/agents"

const labels: Record<RunStatus, string> = {
  success: "OK",
  error: "Ошибка",
  pending: "В работе",
}

const tones: Record<RunStatus, string> = {
  success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  error: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
  pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
}

export function RunStatusBadge({ status, className }: { status: RunStatus; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium",
        tones[status],
        className
      )}
    >
      {labels[status]}
    </span>
  )
}
