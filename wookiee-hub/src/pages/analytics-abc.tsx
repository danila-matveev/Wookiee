import { useMemo } from "react"
import { AbcHeader } from "@/components/analytics/abc-header"
import { AbcTable } from "@/components/analytics/abc-table"
import { AbcChart } from "@/components/analytics/abc-chart"
import { GlobalFilters } from "@/components/dashboard/global-filters"
import { MetricCard } from "@/components/shared/metric-card"
import { useFilterParams } from "@/stores/filters"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchAbcByArticle } from "@/lib/api/abc"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { AbcArticle } from "@/types/api"

export function AnalyticsAbcPage() {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery<AbcArticle[]>(
    () => fetchAbcByArticle({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  const items = data ?? []

  const summary = useMemo(() => {
    const totalRevenue = items.reduce((s, i) => s + i.revenue, 0)
    const totalOrders = items.reduce((s, i) => s + i.orders, 0)
    const totalMargin = items.reduce((s, i) => s + i.margin, 0)
    const weightedMarginPct =
      totalRevenue > 0
        ? items.reduce((s, i) => s + i.margin_pct * i.revenue, 0) / totalRevenue
        : 0
    const totalAdv = items.reduce((s, i) => s + i.adv_total, 0)
    const avgDrr = totalRevenue > 0 ? (totalAdv / totalRevenue) * 100 : 0
    return { totalRevenue, totalOrders, totalMargin, weightedMarginPct, avgDrr }
  }, [items])

  const chartData = useMemo(() => {
    const groups: Record<string, number> = { A: 0, B: 0, C: 0, New: 0 }
    for (const item of items) {
      groups[item.category] = (groups[item.category] ?? 0) + item.revenue
    }
    const total = Object.values(groups).reduce((a, b) => a + b, 0)
    return (["A", "B", "C", "New"] as const).map((cat) => ({
      group: cat,
      revenue: groups[cat],
      share: total > 0 ? +((groups[cat] / total) * 100).toFixed(1) : 0,
    }))
  }, [items])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-bold">ABC-анализ</h1>
        <GlobalFilters />
      </div>

      {/* Summary metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard
          label="Выручка"
          value={formatCurrency(summary.totalRevenue)}
          sub={`${items.length} артикулов`}
        />
        <MetricCard
          label="Заказы"
          value={formatNumber(summary.totalOrders)}
          sub="шт."
        />
        <MetricCard
          label="Маржа"
          value={formatCurrency(summary.totalMargin)}
          sub={formatPercent(summary.weightedMarginPct)}
        />
        <MetricCard
          label="Средний DRR"
          value={formatPercent(summary.avgDrr)}
          sub="расходы на рекламу"
        />
        <MetricCard
          label="Категория A"
          value={`${chartData.find((c) => c.group === "A")?.share ?? 0}%`}
          sub="доля выручки"
        />
      </div>

      {loading && (
        <div className="text-center py-12 text-muted-foreground text-sm">
          Загрузка данных...
        </div>
      )}

      {error && (
        <div className="text-center py-12 text-red-400 text-sm">
          Ошибка: {error}
        </div>
      )}

      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3">
          <AbcTable items={items} />
          <AbcChart data={chartData} />
        </div>
      )}
    </div>
  )
}
