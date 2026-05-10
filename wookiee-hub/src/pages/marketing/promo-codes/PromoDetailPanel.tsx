import { useQuery } from "@tanstack/react-query"
import { Drawer } from "@/components/crm/ui/Drawer"
import { Badge } from "@/components/crm/ui/Badge"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import { fetchPromoStatsForCode } from "@/api/marketing/promo-codes"
import { usePromoCodes } from "@/hooks/marketing/use-promo-codes"
import type { PromoCodeRow, PromoStatWeekly } from "@/types/marketing"

interface PromoDetailPanelProps {
  promoId: number
  onClose: () => void
}

const fmt  = (n: number) => n.toLocaleString('ru-RU')
const fmtR = (n: number) => `${n.toLocaleString('ru-RU')} ₽`

const lCls = "block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1"

export function PromoDetailPanel({ promoId, onClose }: PromoDetailPanelProps) {
  const { data: promos = [], isLoading: promosLoading } = usePromoCodes()
  const { data: weekly = [], isLoading: weeklyLoading, error: weeklyError } = useQuery<PromoStatWeekly[]>({
    queryKey: ['marketing', 'promo-codes', 'for-code', promoId],
    queryFn: () => fetchPromoStatsForCode(promoId),
    enabled: promoId > 0,
    staleTime: 60_000,
  })
  const promo: PromoCodeRow | undefined = promos.find((p) => p.id === promoId)
  const qty   = weekly.reduce((s, w) => s + w.orders_count, 0)
  const sales = weekly.reduce((s, w) => s + w.sales_rub, 0)
  const avg   = qty > 0 ? Math.round(sales / qty) : 0

  return (
    <Drawer open={true} onClose={onClose} title={promo?.code ?? 'Промокод'}>
      {promosLoading ? (
        <div className="text-sm text-muted-foreground p-4">Загрузка…</div>
      ) : !promo ? (
        <EmptyState title="Промокод не найден" description="Возможно, он удалён или ID неверен." />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-1.5">
            <Badge tone={promo.status === 'unidentified' ? 'warning' : promo.status === 'archive' ? 'secondary' : 'success'}>
              {promo.status === 'unidentified' ? 'Не идентиф.' : promo.status === 'archive' ? 'Архив' : 'Активен'}
            </Badge>
            {promo.channel && <Badge tone="secondary">{promo.channel}</Badge>}
          </div>

          <div className="space-y-3">
            <div>
              <div className={lCls}>Код</div>
              <div className="font-mono text-xs text-foreground break-all">{promo.code}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className={lCls}>Канал</div>
                <div className="text-sm text-foreground">{promo.channel ?? '—'}</div>
              </div>
              <div>
                <div className={lCls}>Скидка %</div>
                <div className="text-sm tabular-nums text-foreground">{promo.discount_pct != null ? `${promo.discount_pct}%` : '—'}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className={lCls}>Начало</div>
                <div className="text-sm tabular-nums text-foreground">{promo.valid_from ?? '—'}</div>
              </div>
              <div>
                <div className={lCls}>Окончание</div>
                <div className="text-sm tabular-nums text-foreground">{promo.valid_until ?? '—'}</div>
              </div>
            </div>
            {promo.notes && (
              <div>
                <div className={lCls}>Заметки</div>
                <div className="text-sm text-foreground whitespace-pre-wrap">{promo.notes}</div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3 pt-3 border-t border-border">
            <div>
              <div className={lCls}>Продажи, шт</div>
              <div className="text-lg font-medium text-foreground tabular-nums">{fmt(qty)}</div>
            </div>
            <div>
              <div className={lCls}>Продажи, ₽</div>
              <div className="text-lg font-medium text-foreground tabular-nums">{fmtR(sales)}</div>
            </div>
            <div>
              <div className={lCls}>Ср. чек, ₽</div>
              <div className="text-lg font-medium text-foreground tabular-nums">{avg > 0 ? fmtR(avg) : '—'}</div>
            </div>
          </div>

          <div className="pt-3 border-t border-border">
            <div className={lCls + ' mb-2'}>По неделям</div>
            {weeklyLoading ? (
              <div className="text-sm text-muted-foreground">Загрузка…</div>
            ) : weeklyError ? (
              <EmptyState title="Ошибка загрузки" description="Не удалось загрузить данные по неделям." />
            ) : weekly.length === 0 ? (
              <EmptyState title="По неделям" description="Данные появятся после понедельника." />
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-1 text-[10px] uppercase text-muted-foreground font-medium">Нед</th>
                    <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Зак.</th>
                    <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Продажи</th>
                    <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Возвр.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {weekly.map((w) => (
                    <tr key={w.week_start}>
                      <td className="py-1.5 tabular-nums text-muted-foreground">{w.week_start}</td>
                      <td className="py-1.5 text-right tabular-nums text-foreground font-medium">{w.orders_count}</td>
                      <td className="py-1.5 text-right tabular-nums text-foreground/80">{fmtR(w.sales_rub)}</td>
                      <td className="py-1.5 text-right tabular-nums text-muted-foreground">{w.returns_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="pt-3 border-t border-border">
            <EmptyState title="Товарная разбивка" description="Появится в Phase 2 после backfill источников выкупов." />
          </div>
        </div>
      )}
    </Drawer>
  )
}
