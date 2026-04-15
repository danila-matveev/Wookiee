import { useMemo } from "react"
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchAdDailySeries } from "@/lib/api/promo"
import { useFilterParams } from "@/stores/filters"
import { formatNumber, formatPercent } from "@/lib/format"
import { format, parseISO } from "date-fns"
import { ru } from "date-fns/locale"
import type { AdDailySeries } from "@/types/api"

interface ChartPoint {
  date: string
  orders: number
  drr_pct: number
}

function transformData(series: AdDailySeries[]): ChartPoint[] {
  return series.map((d) => ({
    date: format(parseISO(d.date), "d MMM", { locale: ru }),
    orders: d.ad_orders,
    drr_pct: d.drr_pct,
  }))
}

export function PromoChart() {
  const params = useFilterParams()

  const { data, loading } = useApiQuery<AdDailySeries[]>(
    () => fetchAdDailySeries({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  const chartData = useMemo(() => (data ? transformData(data) : []), [data])

  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[13px] font-semibold">Заказы и ДРР по дням</h3>
        <div className="flex gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "var(--accent)" }} />
            Заказы (шт)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "var(--wk-red)" }} />
            ДРР %
          </span>
        </div>
      </div>

      {loading ? (
        <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm animate-pulse">
          Загрузка графика...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--text-dim)" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: "var(--text-dim)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => formatNumber(Math.round(v))}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: "var(--text-dim)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value: number, name: string) => {
                if (name === "orders") return [formatNumber(value), "Заказы"]
                return [formatPercent(value), "ДРР"]
              }}
              labelStyle={{ color: "var(--muted-foreground)", fontSize: 11 }}
            />
            <Legend
              verticalAlign="bottom"
              height={30}
              formatter={(value: string) => {
                if (value === "orders") return "Заказы (шт)"
                if (value === "drr_pct") return "ДРР %"
                return value
              }}
              wrapperStyle={{ fontSize: 11 }}
            />

            <Area
              yAxisId="right"
              type="monotone"
              dataKey="drr_pct"
              fill="var(--wk-red)"
              fillOpacity={0.1}
              stroke="var(--wk-red)"
              strokeWidth={1.5}
              name="drr_pct"
              connectNulls
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="orders"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={false}
              name="orders"
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
