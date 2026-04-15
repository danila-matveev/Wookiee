import { cn } from "@/lib/utils"
import { quickStats } from "@/data/dashboard-mock"
import { formatCurrency } from "@/lib/format"

export function QuickStats({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Balance Card */}
      <div className="bg-card border border-border rounded-[10px] p-4">
        <div className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-2">
          Баланс
        </div>
        <div className="text-[24px] font-bold leading-tight tabular-nums">
          {formatCurrency(quickStats.balance.value)}
        </div>
        <div className="text-[12px] text-wk-green mt-1">
          {quickStats.balance.sub}
        </div>
      </div>

      {/* WB Rating Card */}
      <div className="bg-card border border-border rounded-[10px] p-4">
        <div className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-2">
          Рейтинг WB
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-[28px] font-bold leading-tight tabular-nums">{quickStats.rating.value}</span>
          <span className="text-[14px] text-muted-foreground">/ {quickStats.rating.maxValue}</span>
        </div>
        <div className="text-[13px] text-muted-foreground mt-1">
          Выкуп {quickStats.rating.buyoutRate}%
        </div>
      </div>
    </div>
  )
}
