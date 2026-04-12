import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { formatNumber, formatCurrency } from "@/lib/format"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchDailySeries } from "@/lib/api/series"
import { useFilterParams } from "@/stores/filters"
import type { DailySeries } from "@/types/api"

function ChartSkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="h-[200px] w-full" />
    </div>
  )
}

interface ChartPoint {
  date: string
  orders: number
  sales: number
}

function mapSeries(raw: DailySeries[]): ChartPoint[] {
  return raw.map((d) => {
    const dt = new Date(d.date)
    const label = `${String(dt.getDate()).padStart(2, "0")}.${String(dt.getMonth() + 1).padStart(2, "0")}`
    return {
      date: label,
      orders: d.revenue_before_spp,
      sales: d.margin,
    }
  })
}

export function OrdersChart({ className }: { className?: string }) {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery(
    () => fetchDailySeries({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      {loading ? (
        <ChartSkeleton />
      ) : error ? (
        <div className="text-muted-foreground text-sm text-center py-8">{error}</div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Заказы и маржа</h3>
            <div className="flex gap-3 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent" />
                Заказы до СПП
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-wk-green" />
                Маржа
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={mapSeries(data ?? [])}>
              <defs>
                <linearGradient id="ordersGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="marginGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--wk-green)" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="var(--wk-green)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "var(--text-dim)", style: { fontVariantNumeric: "tabular-nums" } }}
                axisLine={{ stroke: "var(--border)" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--text-dim)", style: { fontVariantNumeric: "tabular-nums" } }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${Math.round(v / 1000)}K`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number, name: string) => [
                  formatCurrency(value),
                  name === "orders" ? "Заказы до СПП" : "Маржа",
                ]}
                labelStyle={{ color: "var(--muted-foreground)", fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="orders"
                stroke="var(--accent)"
                fill="url(#ordersGrad)"
                strokeWidth={2}
                name="orders"
              />
              <Area
                type="monotone"
                dataKey="sales"
                stroke="var(--wk-green)"
                fill="url(#marginGrad)"
                strokeWidth={2}
                name="sales"
              />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
