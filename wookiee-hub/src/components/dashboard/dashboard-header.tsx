import { cn } from "@/lib/utils"
import { GlobalFilters } from "./global-filters"

export function DashboardHeader({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 flex-wrap", className)}>
      <div>
        <h1 className="text-[22px] font-bold">Dashboard</h1>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Сводка по маркетплейсам
        </p>
      </div>
      <GlobalFilters />
    </div>
  )
}
