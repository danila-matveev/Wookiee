import { motion, useReducedMotion } from "motion/react"
import { MetricCard } from "@/components/shared/metric-card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { staggerContainer, staggerItem } from "@/lib/motion"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceSummary } from "@/lib/api/finance"
import { fetchStocksSummary } from "@/lib/api/stocks"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { DashboardMetric } from "@/types/dashboard"
import type { FinanceSummary, StocksSummary } from "@/types/api"

function pctChange(current: number, previous: number): string | undefined {
  if (!previous) return undefined
  const pct = ((current - previous) / Math.abs(previous)) * 100
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`
}

function buildMetrics(
  fin: FinanceSummary,
  stocks: StocksSummary | null,
): DashboardMetric[] {
  const c = fin.current
  const p = fin.previous

  return [
    {
      label: "Заказы до СПП",
      value: formatCurrency(c.orders_rub),
      sub: `${formatNumber(c.orders_count)} заказов`,
      change: pctChange(c.orders_rub, p.orders_rub),
      positive: c.orders_rub >= p.orders_rub,
    },
    {
      label: "Маржа",
      value: formatCurrency(c.margin),
      sub: formatPercent(c.margin_pct),
      change: pctChange(c.margin, p.margin),
      positive: c.margin >= p.margin,
    },
    {
      label: "Остаток FBO",
      value: stocks ? formatCurrency(stocks.fbo_value) : "...",
      sub: stocks
        ? `${formatNumber(stocks.fbo_count)} шт`
        : "загрузка...",
    },
    {
      label: "Продажи до СПП",
      value: formatCurrency(c.revenue_before_spp),
      sub: `${formatNumber(c.sales_count)} продаж`,
      change: pctChange(c.revenue_before_spp, p.revenue_before_spp),
      positive: c.revenue_before_spp >= p.revenue_before_spp,
    },
    {
      label: "Ср.чек заказа",
      value: c.orders_count
        ? formatCurrency(Math.round(c.orders_rub / c.orders_count))
        : "0",
      sub: "до СПП",
      change: (() => {
        const curAvg = c.orders_count ? c.orders_rub / c.orders_count : 0
        const prevAvg = p.orders_count ? p.orders_rub / p.orders_count : 0
        return pctChange(curAvg, prevAvg)
      })(),
      positive: (() => {
        const curAvg = c.orders_count ? c.orders_rub / c.orders_count : 0
        const prevAvg = p.orders_count ? p.orders_rub / p.orders_count : 0
        return curAvg >= prevAvg
      })(),
    },
    {
      label: "Маржа %",
      value: formatPercent(c.margin_pct),
      sub: "от продаж до СПП",
      change: pctChange(c.margin_pct, p.margin_pct),
      positive: c.margin_pct >= p.margin_pct,
    },
  ]
}

function MetricCardSkeleton() {
  return (
    <div className="bg-card border border-border rounded-[10px] p-4 space-y-3">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-3 w-20" />
    </div>
  )
}

export function DashboardMetrics({ className }: { className?: string }) {
  const reducedMotion = useReducedMotion()
  const params = useFilterParams()

  const { data: finance, loading: finLoading, error: finError } = useApiQuery(
    () => fetchFinanceSummary({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  const { data: stocks } = useApiQuery(
    () => fetchStocksSummary({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  if (finLoading) {
    return (
      <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3", className)}>
        {Array.from({ length: 6 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (finError || !finance) {
    return (
      <div className={cn("bg-card border border-border rounded-[10px] p-6 text-center text-muted-foreground", className)}>
        {finError ?? "Не удалось загрузить метрики"}
      </div>
    )
  }

  const metrics = buildMetrics(finance, stocks)

  return (
    <motion.div
      className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3", className)}
      variants={reducedMotion ? undefined : staggerContainer}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
    >
      {metrics.map((metric) => (
        <motion.div key={metric.label} variants={reducedMotion ? undefined : staggerItem}>
          <MetricCard {...metric} />
        </motion.div>
      ))}
    </motion.div>
  )
}
