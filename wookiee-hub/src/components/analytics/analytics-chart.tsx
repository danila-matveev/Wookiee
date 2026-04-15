import { useMemo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts"
import { cn } from "@/lib/utils"
import { formatCurrency, formatNumber } from "@/lib/format"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchDailySeries } from "@/lib/api/series"
import { useFilterParams } from "@/stores/filters"
import { subDays, differenceInDays, format, parseISO } from "date-fns"
import { ru } from "date-fns/locale"
import type { DailySeries } from "@/types/api"

const tabs = [
  { id: "revenue", label: "Выручка" },
  { id: "margin", label: "Маржа" },
  { id: "orders", label: "Заказы" },
  { id: "advertising", label: "Реклама" },
]

interface TabConfig {
  dataKey: string
  prevDataKey: string
  color: string
  prevColor: string
  label: string
  prevLabel: string
  formatter: (v: number) => string
  yAxisFormatter: (v: number) => string
}

function getTabConfig(tabId: string): TabConfig {
  switch (tabId) {
    case "revenue":
      return {
        dataKey: "revenue_before_spp",
        prevDataKey: "prev_revenue_before_spp",
        color: "var(--accent)",
        prevColor: "var(--muted-foreground)",
        label: "Выручка",
        prevLabel: "Пред. период",
        formatter: (v) => formatCurrency(v),
        yAxisFormatter: (v) => `${Math.round(v / 1000)}K`,
      }
    case "margin":
      return {
        dataKey: "margin",
        prevDataKey: "prev_margin",
        color: "var(--wk-green)",
        prevColor: "var(--muted-foreground)",
        label: "Маржа",
        prevLabel: "Пред. период",
        formatter: (v) => formatCurrency(v),
        yAxisFormatter: (v) => `${Math.round(v / 1000)}K`,
      }
    case "orders":
      return {
        dataKey: "orders_count",
        prevDataKey: "prev_orders_count",
        color: "var(--accent)",
        prevColor: "var(--muted-foreground)",
        label: "Заказы",
        prevLabel: "Пред. период",
        formatter: (v) => formatNumber(v),
        yAxisFormatter: (v) => formatNumber(Math.round(v)),
      }
    case "advertising":
      return {
        dataKey: "adv_total",
        prevDataKey: "prev_adv_total",
        color: "var(--wk-red)",
        prevColor: "var(--muted-foreground)",
        label: "Реклама",
        prevLabel: "Пред. период",
        formatter: (v) => formatCurrency(v),
        yAxisFormatter: (v) => `${Math.round(v / 1000)}K`,
      }
    default:
      return getTabConfig("revenue")
  }
}

interface AnalyticsChartProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

/** Merge current and previous period series by day index for overlay */
function mergeSeriesForOverlay(
  currentSeries: DailySeries[],
  previousSeries: DailySeries[],
): Record<string, unknown>[] {
  const maxLen = Math.max(currentSeries.length, previousSeries.length)
  const merged: Record<string, unknown>[] = []

  for (let i = 0; i < maxLen; i++) {
    const cur = currentSeries[i]
    const prev = previousSeries[i]

    const point: Record<string, unknown> = {
      dayIndex: i,
      date: cur ? format(parseISO(cur.date), "d MMM", { locale: ru }) : prev ? `День ${i + 1}` : "",
    }

    if (cur) {
      point.revenue_before_spp = cur.revenue_before_spp
      point.margin = cur.margin
      point.orders_count = cur.orders_count
      point.adv_total = cur.adv_total
    }
    if (prev) {
      point.prev_revenue_before_spp = prev.revenue_before_spp
      point.prev_margin = prev.margin
      point.prev_orders_count = prev.orders_count
      point.prev_adv_total = prev.adv_total
    }

    merged.push(point)
  }

  return merged
}

export function AnalyticsChart({ activeTab, onTabChange }: AnalyticsChartProps) {
  const params = useFilterParams()

  // Compute previous period dates (same length, shifted back)
  const periodDays = useMemo(() => {
    const from = parseISO(params.start_date)
    const to = parseISO(params.end_date)
    return differenceInDays(to, from) + 1
  }, [params.start_date, params.end_date])

  const prevDates = useMemo(() => {
    const from = parseISO(params.start_date)
    const prevEnd = subDays(from, 1)
    const prevStart = subDays(prevEnd, periodDays - 1)
    return {
      start_date: format(prevStart, "yyyy-MM-dd"),
      end_date: format(prevEnd, "yyyy-MM-dd"),
    }
  }, [params.start_date, periodDays])

  // Fetch current period daily series
  const { data: currentData, loading: loadingCurrent } = useApiQuery<DailySeries[]>(
    () => fetchDailySeries({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  // Fetch previous period daily series
  const { data: prevData, loading: loadingPrev } = useApiQuery<DailySeries[]>(
    () => fetchDailySeries({ start_date: prevDates.start_date, end_date: prevDates.end_date, mp: params.mp }),
    [prevDates.start_date, prevDates.end_date, params.mp],
  )

  const loading = loadingCurrent || loadingPrev

  const chartData = useMemo(() => {
    if (!currentData) return []
    return mergeSeriesForOverlay(currentData, prevData ?? [])
  }, [currentData, prevData])

  const config = getTabConfig(activeTab)

  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-4 border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={cn(
                "pb-2 text-[13px] font-medium transition-colors",
                tab.id === activeTab
                  ? "text-foreground border-b-2 border-accent"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
            {config.label}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-muted-foreground" />
            {config.prevLabel}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm animate-pulse">
          Загрузка графика...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--text-dim)" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--text-dim)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={config.yAxisFormatter}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value: number, name: string) => {
                const label = name.startsWith("prev_") ? config.prevLabel : config.label
                return [config.formatter(value), label]
              }}
              labelStyle={{ color: "var(--muted-foreground)", fontSize: 11 }}
            />
            <Legend
              verticalAlign="bottom"
              height={30}
              formatter={(value: string) => {
                if (value === config.dataKey) return config.label
                if (value === config.prevDataKey) return config.prevLabel
                return value
              }}
              wrapperStyle={{ fontSize: 11 }}
            />

            {/* Current period line */}
            <Line
              type="monotone"
              dataKey={config.dataKey}
              stroke={config.color}
              strokeWidth={2}
              dot={false}
              name={config.dataKey}
              connectNulls
            />

            {/* Previous period line (overlay) */}
            <Line
              type="monotone"
              dataKey={config.prevDataKey}
              stroke={config.prevColor}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              dot={false}
              name={config.prevDataKey}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
