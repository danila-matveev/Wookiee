import { useApiQuery } from "@/hooks/use-api-query"
import { fetchOrganicVsPaid } from "@/lib/api/traffic"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { OrganicVsPaid } from "@/types/api"

export function PromoFunnelTab() {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery<OrganicVsPaid>(
    () => fetchOrganicVsPaid({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-[10px] p-4 animate-pulse h-[200px]" />
    )
  }

  if (error) {
    return (
      <div className="bg-card border border-wk-red/30 rounded-[10px] p-4 text-wk-red text-sm">
        Ошибка: {error}
      </div>
    )
  }

  if (!data) return null

  const rows = [
    {
      label: "Органика",
      orders: data.organic_orders,
      revenue: data.organic_revenue,
      share: 100 - data.paid_share_pct,
    },
    {
      label: "Реклама",
      orders: data.paid_orders,
      revenue: data.paid_revenue,
      share: data.paid_share_pct,
    },
    {
      label: "Итого",
      orders: data.organic_orders + data.paid_orders,
      revenue: data.organic_revenue + data.paid_revenue,
      share: 100,
    },
  ]

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border bg-bg-soft">
            <th className="text-left px-4 py-2.5 font-semibold text-muted-foreground">Канал</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Заказы</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Выручка</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Доля %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.label}
              className={`border-b border-border last:border-0 ${row.label === "Итого" ? "font-semibold bg-bg-soft/50" : "hover:bg-bg-soft/30"}`}
            >
              <td className="px-4 py-2.5">{row.label}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(row.orders)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.revenue)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatPercent(row.share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
