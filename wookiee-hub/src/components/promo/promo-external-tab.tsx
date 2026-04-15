import { useApiQuery } from "@/hooks/use-api-query"
import { fetchExternalBreakdown } from "@/lib/api/traffic"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { ExternalBreakdown } from "@/types/api"

function drrColor(drr: number): string {
  if (drr > 30) return "text-wk-red"
  if (drr > 15) return "text-wk-yellow"
  return "text-wk-green"
}

export function PromoExternalTab() {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery<ExternalBreakdown[]>(
    () => fetchExternalBreakdown({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
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

  if (!data || data.length === 0) {
    return (
      <div className="bg-card border border-border rounded-[10px] p-6 text-center text-muted-foreground text-sm">
        Нет данных по внешнему трафику за выбранный период
      </div>
    )
  }

  const totalSpend = data.reduce((s, r) => s + r.spend, 0)
  const totalOrders = data.reduce((s, r) => s + r.orders, 0)
  const totalRevenue = data.reduce((s, r) => s + r.revenue, 0)
  const totalDrr = totalRevenue > 0 ? (totalSpend / totalRevenue) * 100 : 0

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border bg-bg-soft">
            <th className="text-left px-4 py-2.5 font-semibold text-muted-foreground">Канал</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Расход</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Заказы</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">Выручка</th>
            <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground">ДРР %</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.channel} className="border-b border-border last:border-0 hover:bg-bg-soft/30">
              <td className="px-4 py-2.5 font-medium">{row.channel}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.spend)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(row.orders)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.revenue)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">
                <span className={drrColor(row.drr_pct)}>{formatPercent(row.drr_pct)}</span>
              </td>
            </tr>
          ))}
          <tr className="border-t border-border font-semibold bg-bg-soft/50">
            <td className="px-4 py-2.5">Итого</td>
            <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(totalSpend)}</td>
            <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(totalOrders)}</td>
            <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(totalRevenue)}</td>
            <td className="px-4 py-2.5 text-right tabular-nums">
              <span className={drrColor(totalDrr)}>{formatPercent(totalDrr)}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
