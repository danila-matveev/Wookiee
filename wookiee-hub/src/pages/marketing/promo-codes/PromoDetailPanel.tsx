import { useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
import { Drawer } from "@/components/crm/ui/Drawer"
import { Badge } from "@/components/crm/ui/Badge"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import { fetchPromoStatsForCode } from "@/api/marketing/promo-codes"
import { usePromoCodes } from "@/hooks/marketing/use-promo-codes"
import type { PromoCodeRow, PromoStatWeekly } from "@/types/marketing"

interface PromoDetailPanelProps {
  promoId: number
  onClose: () => void
  /** 'inline' renders bare content for split-pane host; 'drawer' (default) wraps in Drawer. */
  mode?: 'drawer' | 'inline'
}

const fmt  = (n: number) => n.toLocaleString('ru-RU')
const fmtR = (n: number) => `${n.toLocaleString('ru-RU')} ₽`

const lCls = "block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1"

export function PromoDetailPanel({ promoId, onClose, mode = 'drawer' }: PromoDetailPanelProps) {
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

  const body = (
    promosLoading ? (
      <div className="text-sm text-muted-foreground p-4">Загрузка…</div>
    ) : !promo ? (
      <EmptyState title="Промокод не найден" description="Возможно, он удалён или ID неверен." />
    ) : (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5">
          <Badge tone={promo.status === 'expired' ? 'warning' : promo.status === 'archived' ? 'secondary' : promo.status === 'paused' ? 'info' : 'success'}>
            {promo.status === 'expired' ? 'Истёк' : promo.status === 'archived' ? 'Архив' : promo.status === 'paused' ? 'На паузе' : 'Активен'}
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
    )
  )

  if (mode === 'inline') {
    return (
      <div className="flex flex-col h-full">
        <header className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
          <h2 className="font-semibold text-lg text-fg truncate">{promo?.code ?? 'Промокод'}</h2>
          <button
            type="button"
            aria-label="Закрыть"
            className="p-2 rounded-md hover:bg-primary-light cursor-pointer"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-4">{body}</div>
      </div>
    )
  }

  return (
    <Drawer open={true} onClose={onClose} title={promo?.code ?? 'Промокод'}>
      {body}
    </Drawer>
  )
}
