import { MetricCard } from "@/components/shared/metric-card"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceSummary } from "@/lib/api/finance"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { FinanceSummary, PeriodFinance } from "@/types/api"
import type { DashboardMetric } from "@/types/dashboard"

/** Compute percentage change between two values */
function pctChange(current: number, previous: number): number | null {
  if (previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}

/** Build a metric card descriptor from current vs previous period */
function buildMetric(
  label: string,
  currentVal: number,
  previousVal: number,
  formatter: (v: number) => string,
  sub: string,
  positiveIsUp = true,
): DashboardMetric {
  const change = pctChange(currentVal, previousVal)
  const changeStr = change !== null ? `${change >= 0 ? "+" : ""}${change.toFixed(1)}%` : undefined
  const isPositive = change !== null ? (positiveIsUp ? change >= 0 : change <= 0) : undefined

  return {
    label,
    value: formatter(currentVal),
    sub,
    change: changeStr,
    positive: isPositive,
  }
}

function buildMetrics(summary: FinanceSummary): DashboardMetric[] {
  const cur: PeriodFinance = summary.current
  const prev: PeriodFinance = summary.previous

  return [
    buildMetric("Выручка", cur.revenue_before_spp, prev.revenue_before_spp, (v) => formatCurrency(v), "До СПП"),
    buildMetric("Маржа", cur.margin, prev.margin, (v) => formatCurrency(v), `Рент. ${formatPercent(cur.margin_pct)}`),
    buildMetric("Заказы", cur.orders_count, prev.orders_count, (v) => formatNumber(v), `${formatNumber(cur.orders_rub)} ₽`),
    buildMetric("Продажи", cur.sales_count, prev.sales_count, (v) => formatNumber(v), `Выр. после СПП ${formatCurrency(cur.revenue_after_spp)}`),
    buildMetric("Реклама", cur.adv_internal + cur.adv_external, prev.adv_internal + prev.adv_external, (v) => formatCurrency(v), "Внутренняя + внешняя", false),
    buildMetric("Логистика", cur.logistics, prev.logistics, (v) => formatCurrency(v), "Доставка", false),
    buildMetric("Хранение", cur.storage, prev.storage, (v) => formatCurrency(v), "Склады МП", false),
    buildMetric("Комиссия", cur.commission, prev.commission, (v) => formatCurrency(v), "Комиссия МП", false),
  ]
}

export function AnalyticsMetrics() {
  const params = useFilterParams()
  const { data, loading, error } = useApiQuery<FinanceSummary>(
    () => fetchFinanceSummary({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-[10px] p-4 animate-pulse h-[100px]" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-card border border-wk-red/30 rounded-[10px] p-4 text-wk-red text-sm">
        Ошибка загрузки метрик: {error}
      </div>
    )
  }

  if (!data) return null

  const metrics = buildMetrics(data)

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} {...metric} />
      ))}
    </div>
  )
}
