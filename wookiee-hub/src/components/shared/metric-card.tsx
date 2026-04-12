import { cn } from "@/lib/utils"
import { ChangeIndicator } from "./change-indicator"
import { ProgressBar } from "./progress-bar"
import type { DashboardMetric } from "@/types/dashboard"

interface MetricCardProps extends DashboardMetric {
  className?: string
}

export function MetricCard({
  label,
  value,
  sub,
  change,
  positive,
  plan,
  forecast,
  className,
}: MetricCardProps) {
  // Calculate progress percentage if plan is provided
  const progressValue = plan
    ? (() => {
        const numValue = parseFloat(value.replace(/[^\d.,]/g, "").replace(/\s/g, "").replace(",", "."))
        const numPlan = parseFloat(plan.replace(/[^\d.,]/g, "").replace(/\s/g, "").replace(",", "."))
        return numPlan > 0 ? (numValue / numPlan) * 100 : 0
      })()
    : undefined

  return (
    <div
      className={cn(
        "bg-card border border-border rounded-[10px] p-4 transition-all duration-150",
        "hover:border-accent-border hover:shadow-glow",
        className
      )}
    >
      <div className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-2">
        {label}
      </div>
      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-[22px] font-bold leading-tight tabular-nums">{value}</span>
        {change && <ChangeIndicator value={change} positive={positive} />}
      </div>
      <div className="text-[12px] text-muted-foreground">{sub}</div>
      {progressValue !== undefined && (
        <div className="mt-3 space-y-1">
          <ProgressBar value={progressValue} />
          <div className="flex justify-between text-[11px] text-text-dim">
            <span>План: {plan}</span>
            {forecast && <span>Прогноз: {forecast}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
