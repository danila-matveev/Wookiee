import { cn } from "@/lib/utils"
import { getServiceDef } from "@/config/service-registry"
import { commsAnalyticsStores } from "@/data/community-mock"
import { formatPercent } from "@/lib/format"

function formatMinutes(value: number): string {
  if (value < 60) return `${Math.round(value)}м`
  const hours = Math.floor(value / 60)
  const mins = Math.round(value % 60)
  if (mins === 0) return `${hours}ч`
  return `${hours}ч ${mins}м`
}

export function AnalyticsStoresTable({ className }: { className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <h3 className="text-sm font-semibold mb-3">Разбивка по магазинам</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="pb-2 pr-4 font-semibold">Магазин</th>
              <th className="pb-2 pr-4 font-semibold text-right">Отзывы</th>
              <th className="pb-2 pr-4 font-semibold text-right">Вопросы</th>
              <th className="pb-2 pr-4 font-semibold text-right">Ср. время</th>
              <th className="pb-2 pr-4 font-semibold text-right">% отвечено</th>
              <th className="pb-2 font-semibold text-right">Ср. рейтинг</th>
            </tr>
          </thead>
          <tbody>
            {commsAnalyticsStores.map((store) => {
              const def = getServiceDef(store.serviceType)
              return (
                <tr key={store.connectionId} className="border-b border-border/50 last:border-0">
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                        style={{ backgroundColor: def.color }}
                      >
                        {def.label.slice(0, 2).toUpperCase()}
                      </div>
                      <span className="font-medium text-[13px]">{store.name}</span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{store.reviews}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{store.questions}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{formatMinutes(store.avgResponseMin)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{formatPercent(store.responseRate)}</td>
                  <td className="py-2.5 text-right tabular-nums">{store.avgRating.toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
