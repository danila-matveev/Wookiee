import { MetricCard } from "@/components/shared/metric-card"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchTrafficSummary } from "@/lib/api/traffic"
import { fetchFinanceSummary } from "@/lib/api/finance"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatPercent } from "@/lib/format"
import type { TrafficSummary, FinanceSummary } from "@/types/api"
import type { DashboardMetric } from "@/types/dashboard"

function pctChange(current: number, previous: number): number | null {
  if (previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}

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

function buildPromoMetrics(
  traffic: TrafficSummary,
  finance: FinanceSummary,
): DashboardMetric[] {
  const cur = traffic.current
  const prev = traffic.previous
  const finCur = finance.current
  const finPrev = finance.previous

  const curDrrOrders =
    finCur.orders_rub > 0 ? (finCur.adv_internal / finCur.orders_rub) * 100 : 0
  const prevDrrOrders =
    finPrev.orders_rub > 0 ? (finPrev.adv_internal / finPrev.orders_rub) * 100 : 0

  const curCrClickOrder =
    cur.ad_clicks > 0 ? (cur.ad_orders / cur.ad_clicks) * 100 : 0
  const prevCrClickOrder =
    prev.ad_clicks > 0 ? (prev.ad_orders / prev.ad_clicks) * 100 : 0

  const curCrClickOrderAd =
    cur.ad_clicks > 0 ? (cur.funnel_orders / cur.ad_clicks) * 100 : 0
  const prevCrClickOrderAd =
    prev.ad_clicks > 0 ? (prev.funnel_orders / prev.ad_clicks) * 100 : 0

  return [
    buildMetric(
      "Реклама внутр. ₽",
      finCur.adv_internal,
      finPrev.adv_internal,
      (v) => formatCurrency(v),
      "Внутренняя реклама",
      false,
    ),
    buildMetric(
      "ДРР от заказов %",
      curDrrOrders,
      prevDrrOrders,
      (v) => formatPercent(v),
      "Доля рекл. расходов",
      false,
    ),
    buildMetric(
      "CR клик → заказ %",
      curCrClickOrder,
      prevCrClickOrder,
      (v) => formatPercent(v),
      "Конверсия из клика",
    ),
    buildMetric(
      "CR клик → заказ рекл. %",
      curCrClickOrderAd,
      prevCrClickOrderAd,
      (v) => formatPercent(v),
      "Рекламные заказы",
    ),
    buildMetric(
      "CTR реклама %",
      cur.ctr,
      prev.ctr,
      (v) => formatPercent(v),
      `CPC: ${formatCurrency(cur.cpc)}`,
    ),
  ]
}

export function PromoHeader() {
  const params = useFilterParams()
  const queryParams = { start_date: params.start_date, end_date: params.end_date, mp: params.mp }

  const { data: trafficData, loading: loadingTraffic } = useApiQuery<TrafficSummary>(
    () => fetchTrafficSummary(queryParams),
    [params.start_date, params.end_date, params.mp],
  )

  const { data: financeData, loading: loadingFinance } = useApiQuery<FinanceSummary>(
    () => fetchFinanceSummary(queryParams),
    [params.start_date, params.end_date, params.mp],
  )

  const loading = loadingTraffic || loadingFinance

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-[10px] p-4 animate-pulse h-[100px]" />
        ))}
      </div>
    )
  }

  if (!trafficData || !financeData) return null

  const metrics = buildPromoMetrics(trafficData, financeData)

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} {...metric} />
      ))}
    </div>
  )
}
