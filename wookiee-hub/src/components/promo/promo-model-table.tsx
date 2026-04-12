import { useApiQuery } from "@/hooks/use-api-query"
import { fetchPromoModelRoi } from "@/lib/api/promo"
import { useFilterParams } from "@/stores/filters"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import type { PromoModelRow } from "@/types/api"

function drrColor(drr: number): string {
  if (drr > 30) return "text-wk-red"
  if (drr > 15) return "text-wk-yellow"
  return "text-wk-green"
}

export function PromoModelTable() {
  const params = useFilterParams()

  const { data, loading, error } = useApiQuery<PromoModelRow[]>(
    () => fetchPromoModelRoi({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
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
              <th className="text-left px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap sticky left-0 bg-bg-soft z-10">Модель</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Реклама итого ₽</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Заказы рекл.</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">ДРР от заказов %</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">ROMI %</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Реклама внутр.</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Реклама внеш.</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Реклама блогеры</th>
              <th className="text-right px-4 py-2.5 font-semibold text-muted-foreground whitespace-nowrap">Реклама ВК</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.model} className="border-b border-border last:border-0 hover:bg-bg-soft/30">
                <td className="px-4 py-2.5 whitespace-nowrap font-medium sticky left-0 bg-card z-10">{row.model}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.ad_spend)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(row.ad_orders)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  <span className={drrColor(row.drr_pct)}>{formatPercent(row.drr_pct)}</span>
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatPercent(row.romi_pct)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.adv_internal)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.adv_external)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.adv_bloggers)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatCurrency(row.adv_vk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
