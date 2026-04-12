import { useMemo } from "react"
import { GlobalFilters } from "@/components/dashboard/global-filters"
import { MetricCard } from "@/components/shared/metric-card"
import { UnitTable } from "@/components/unit/unit-table"
import type { UnitRow } from "@/components/unit/unit-table"
import { useFilterParams } from "@/stores/filters"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceByModel } from "@/lib/api/finance"
import { fetchStocksTurnover } from "@/lib/api/stocks"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { ModelRow, TurnoverRow } from "@/types/api"

export function AnalyticsUnitPage() {
  const params = useFilterParams()
  const queryParams = { start_date: params.start_date, end_date: params.end_date, mp: params.mp }

  const { data: financeData, loading: finLoading, error: finError } = useApiQuery<ModelRow[]>(
    () => fetchFinanceByModel(queryParams),
    [params.start_date, params.end_date, params.mp],
  )

  const { data: turnoverData, loading: toLoading, error: toError } = useApiQuery<TurnoverRow[]>(
    () => fetchStocksTurnover(queryParams),
    [params.start_date, params.end_date, params.mp],
  )

  const loading = finLoading || toLoading
  const error = finError || toError

  // Build per-model unit economics rows
  const rows = useMemo<UnitRow[]>(() => {
    if (!financeData) return []

    // Only current-period data
    const currentRows = financeData.filter((r) => r.period === "current")

    // Build turnover lookup by lower-cased model name
    const turnoverMap = new Map<string, TurnoverRow>()
    if (turnoverData) {
      for (const t of turnoverData) {
        turnoverMap.set(t.model.toLowerCase(), t)
      }
    }

    return currentRows
      .filter((r) => r.sales_count > 0)
      .map((r) => {
        const sc = r.sales_count
        const turnover = turnoverMap.get(r.model.toLowerCase())
        return {
          model: r.model,
          sales_count: sc,
          revenue_per_unit: r.revenue_before_spp / sc,
          cogs_per_unit: r.cost_of_goods / sc,
          ad_per_unit: (r.adv_internal + r.adv_external) / sc,
          margin_per_unit: r.margin / sc,
          margin_pct: r.margin_pct,
          drr_pct: r.drr_pct,
          turnover_days: turnover?.turnover_days ?? null,
          avg_stock: turnover?.avg_stock ?? null,
        }
      })
  }, [financeData, turnoverData])

  // Summary KPIs (weighted averages where appropriate)
  const summary = useMemo(() => {
    const totalSales = rows.reduce((s, r) => s + r.sales_count, 0)
    const totalRevenue = rows.reduce((s, r) => s + r.revenue_per_unit * r.sales_count, 0)
    const totalMargin = rows.reduce((s, r) => s + r.margin_per_unit * r.sales_count, 0)
    const totalAd = rows.reduce((s, r) => s + r.ad_per_unit * r.sales_count, 0)

    const avgRevenuePerUnit = totalSales > 0 ? totalRevenue / totalSales : 0
    const avgMarginPerUnit = totalSales > 0 ? totalMargin / totalSales : 0
    const weightedMarginPct =
      totalRevenue > 0
        ? rows.reduce((s, r) => s + r.margin_pct * r.revenue_per_unit * r.sales_count, 0) / totalRevenue
        : 0
    const avgDrr = totalRevenue > 0 ? (totalAd / totalRevenue) * 100 : 0

    // Average turnover days (weighted by avg_stock)
    const withTurnover = rows.filter((r) => r.turnover_days != null)
    const totalStock = withTurnover.reduce((s, r) => s + (r.avg_stock ?? 0), 0)
    const avgTurnoverDays =
      totalStock > 0
        ? withTurnover.reduce((s, r) => s + (r.turnover_days ?? 0) * (r.avg_stock ?? 0), 0) / totalStock
        : null

    return { avgRevenuePerUnit, avgMarginPerUnit, weightedMarginPct, avgDrr, avgTurnoverDays }
  }, [rows])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-bold">Unit-экономика</h1>
        <GlobalFilters />
      </div>

      {/* Summary KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard
          label="Выручка / ед."
          value={formatCurrency(Math.round(summary.avgRevenuePerUnit))}
          sub="средневзв."
        />
        <MetricCard
          label="Маржа / ед."
          value={formatCurrency(Math.round(summary.avgMarginPerUnit))}
          sub={formatPercent(summary.weightedMarginPct)}
        />
        <MetricCard
          label="Маржинальность"
          value={formatPercent(summary.weightedMarginPct)}
          sub="средневзв. по выручке"
        />
        <MetricCard
          label="DRR"
          value={formatPercent(summary.avgDrr)}
          sub="расходы на рекламу"
        />
        <MetricCard
          label="Оборачиваемость"
          value={
            summary.avgTurnoverDays != null
              ? `${formatNumber(Math.round(summary.avgTurnoverDays))} дн.`
              : "\u2014"
          }
          sub="средневзв. по остаткам"
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

      {!loading && !error && <UnitTable rows={rows} />}
    </div>
  )
}
