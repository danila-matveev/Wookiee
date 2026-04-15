import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import { formatCurrency } from "@/lib/format"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceSummary } from "@/lib/api/finance"
import { useFilterParams } from "@/stores/filters"
import type { PeriodFinance } from "@/types/api"

interface ExpenseRow {
  name: string
  amount: number
  share: number
  delta: number
}

function buildExpenses(current: PeriodFinance, previous: PeriodFinance): ExpenseRow[] {
  const lines: { name: string; key: keyof PeriodFinance }[] = [
    { name: "Комиссия до СПП", key: "commission" },
    { name: "Себестоимость", key: "cost_of_goods" },
    { name: "Логистика", key: "logistics" },
    { name: "Реклама внутр.", key: "adv_internal" },
    { name: "Хранение", key: "storage" },
    { name: "НДС", key: "nds" },
    { name: "Реклама внешн.", key: "adv_external" },
  ]

  const total = lines.reduce((s, l) => s + (current[l.key] as number), 0)

  return lines
    .map((l) => {
      const cur = current[l.key] as number
      const prev = previous[l.key] as number
      const delta = prev ? ((cur - prev) / Math.abs(prev)) * 100 : 0
      return {
        name: l.name,
        amount: cur,
        share: total ? Math.round((cur / total) * 1000) / 10 : 0,
        delta: Math.round(delta * 10) / 10,
      }
    })
    .filter((r) => r.amount !== 0)
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-20" />
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-6 w-full" />
      ))}
    </div>
  )
}

export function ExpensesTable({ className }: { className?: string }) {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery(
    () => fetchFinanceSummary({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <h3 className="text-sm font-semibold mb-3">Расходы</h3>
      {loading ? (
        <TableSkeleton />
      ) : error || !data ? (
        <div className="text-muted-foreground text-sm text-center py-4">{error ?? "Нет данных"}</div>
      ) : (
        <div className="space-y-0">
          {/* Header */}
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 pb-2 border-b border-border/50">
            <span className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold">Статья</span>
            <span className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold text-right w-20">Сумма</span>
            <span className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold text-right w-10">%</span>
            <span className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold text-right w-14">&Delta;</span>
          </div>
          {/* Rows */}
          {buildExpenses(data.current, data.previous).map((row) => (
            <div
              key={row.name}
              className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 py-2 border-b border-border/20 hover:bg-bg-hover/50 transition-colors duration-100"
            >
              <span className="text-[13px]">{row.name}</span>
              <span className="text-[13px] font-mono tabular-nums text-right w-20">{formatCurrency(row.amount)}</span>
              <span className="text-[12px] text-muted-foreground tabular-nums text-right w-10">{row.share}%</span>
              <span
                className={cn(
                  "text-[11px] font-semibold tabular-nums text-right w-14",
                  row.delta > 0 ? "text-wk-red" : "text-wk-green",
                )}
              >
                {row.delta > 0 ? "\u25B2" : "\u25BC"} {Math.abs(row.delta)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
