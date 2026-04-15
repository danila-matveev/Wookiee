import { useApiQuery } from "@/hooks/use-api-query"
import { fetchAdDailySeries } from "@/lib/api/promo"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import { format, parseISO } from "date-fns"
import { ru } from "date-fns/locale"
import type { AdDailySeries } from "@/types/api"

export function PromoByDatesTab() {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery<AdDailySeries[]>(
    () => fetchAdDailySeries({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-[10px] p-4 animate-pulse h-[300px]" />
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
        Нет данных за выбранный период
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border bg-bg-soft">
              <th className="text-left px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Дата</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Расход</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Заказы</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Выручка</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">ДРР %</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.date} className="border-b border-border last:border-0 hover:bg-bg-soft/30">
                <td className="px-4 py-2.5 whitespace-nowrap">
                  {format(parseISO(row.date), "d MMM yyyy", { locale: ru })}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.ad_spend)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(row.ad_orders)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.ad_revenue)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  <span className={row.drr_pct > 30 ? "text-wk-red" : row.drr_pct > 15 ? "text-wk-yellow" : "text-wk-green"}>
                    {formatPercent(row.drr_pct)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
