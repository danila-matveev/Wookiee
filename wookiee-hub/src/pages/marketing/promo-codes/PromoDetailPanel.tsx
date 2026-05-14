import { useMemo, useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Edit3 } from "lucide-react"
import { Drawer } from "@/components/crm/ui/Drawer"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import { Badge } from "@/components/marketing/Badge"
import { Input } from "@/components/marketing/Input"
import { Button } from "@/components/marketing/Button"
import { SelectMenu } from "@/components/marketing/SelectMenu"
import { fetchPromoStatsForCode } from "@/api/marketing/promo-codes"
import { usePromoCodes, usePromoProductBreakdown, useUpdatePromoCode } from "@/hooks/marketing/use-promo-codes"
import { useChannels } from "@/hooks/marketing/use-channels"
import type { PromoCodeRow, PromoProductBreakdownAgg, PromoStatWeekly } from "@/types/marketing"

interface PromoDetailPanelProps {
  promoId: number
  onClose: () => void
  /** Kept for API compatibility — only 'drawer' is rendered (split-pane removed). */
  mode?: 'drawer'
}

const fmt  = (n: number) => n.toLocaleString('ru-RU')
const fmtR = (n: number) => `${n.toLocaleString('ru-RU')} ₽`
const lCls = "block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1"

type StatusBadge = { label: string; color: 'green' | 'amber' | 'gray' | 'blue' }

function computeStatusBadge(p: PromoCodeRow, qty: number): StatusBadge {
  if (p.status === 'expired')  return { label: 'Истёк',     color: 'amber' }
  if (p.status === 'archived') return { label: 'Архив',     color: 'gray'  }
  if (p.status === 'paused')   return { label: 'На паузе',  color: 'blue'  }
  if (qty === 0)               return { label: 'Нет данных', color: 'gray'  }
  return { label: 'Активен', color: 'green' }
}

interface FormState {
  code: string
  channel: string
  discount_pct: string
  valid_from: string
  valid_until: string
}

const toForm = (p: PromoCodeRow): FormState => ({
  code: p.code,
  channel: p.channel ?? '',
  discount_pct: p.discount_pct != null ? String(p.discount_pct) : '',
  valid_from: p.valid_from ?? '',
  valid_until: p.valid_until ?? '',
})

export function PromoDetailPanel({ promoId, onClose }: PromoDetailPanelProps) {
  const { data: promos = [], isLoading: promosLoading } = usePromoCodes()
  const { data: weekly = [], isLoading: weeklyLoading, error: weeklyError } = useQuery<PromoStatWeekly[]>({
    queryKey: ['marketing', 'promo-codes', 'for-code', promoId],
    queryFn: () => fetchPromoStatsForCode(promoId),
    enabled: promoId > 0,
    staleTime: 60_000,
  })
  const {
    data: breakdownRows = [],
    isLoading: breakdownLoading,
    error: breakdownError,
  } = usePromoProductBreakdown(promoId > 0 ? promoId : null)
  const { data: channels = [] } = useChannels()
  const updateMut = useUpdatePromoCode()

  const promo: PromoCodeRow | undefined = promos.find((p) => p.id === promoId)

  const [isEdit, setIsEdit] = useState(false)
  const [form, setForm] = useState<FormState>(() => promo ? toForm(promo) : { code: '', channel: '', discount_pct: '', valid_from: '', valid_until: '' })

  // Re-sync form when promo data first loads (or promoId switches).
  useEffect(() => {
    if (promo && !isEdit) setForm(toForm(promo))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promo?.id, promo?.code, promo?.channel, promo?.discount_pct, promo?.valid_from, promo?.valid_until])

  const qty   = weekly.reduce((s, w) => s + w.orders_count, 0)
  const sales = weekly.reduce((s, w) => s + w.sales_rub, 0)
  const avg   = qty > 0 ? Math.round(sales / qty) : 0

  const statusBadge = useMemo(() => promo ? computeStatusBadge(promo, qty) : null, [promo, qty])

  // Aggregate weekly breakdown rows by SKU (sum qty + amount) and sort by amount desc.
  const breakdownAgg: PromoProductBreakdownAgg[] = useMemo(() => {
    if (breakdownRows.length === 0) return []
    const map = new Map<string, PromoProductBreakdownAgg>()
    for (const r of breakdownRows) {
      const existing = map.get(r.sku_label)
      if (existing) {
        existing.qty += r.qty
        existing.amount_rub += r.amount_rub
        // Prefer the first non-null model_code we saw.
        if (!existing.model_code && r.model_code) existing.model_code = r.model_code
      } else {
        map.set(r.sku_label, {
          sku_label: r.sku_label,
          model_code: r.model_code,
          qty: r.qty,
          amount_rub: r.amount_rub,
        })
      }
    }
    return Array.from(map.values()).sort((a, b) => b.amount_rub - a.amount_rub)
  }, [breakdownRows])

  const handleSave = async () => {
    if (!promo) return
    await updateMut.mutateAsync({
      id: promo.id,
      code: form.code,
      channel: form.channel || null,
      discount_pct: form.discount_pct === '' ? null : Number(form.discount_pct),
      valid_from: form.valid_from || null,
      valid_until: form.valid_until || null,
    })
    setIsEdit(false)
  }

  const handleCancel = () => {
    if (promo) setForm(toForm(promo))
    setIsEdit(false)
  }

  const body = (
    promosLoading ? (
      <div className="text-sm text-stone-500 p-4">Загрузка…</div>
    ) : !promo ? (
      <EmptyState title="Промокод не найден" description="Возможно, он удалён или ID неверен." />
    ) : (
      // The Drawer wrapper already supplies its own header (with code as title + ✕ close)
      // and an outer scrollable container. We render only secondary metadata (status badge,
      // channel chip, UUID, edit button) and the data sections here.
      <div className="flex flex-col -mx-6 -my-4">
        {/* Meta toolbar: status + channel + UUID + edit */}
        <div className="flex items-start justify-between px-5 py-3 border-b border-stone-200 shrink-0">
          <div className="flex-1 min-w-0 mr-3">
            <div className="flex items-center gap-1.5 flex-wrap">
              {statusBadge && <Badge color={statusBadge.color} label={statusBadge.label} />}
              {promo.channel && (
                <span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[11px] font-medium ring-1 ring-inset ring-stone-500/20">
                  {promo.channel}
                </span>
              )}
            </div>
            {promo.external_uuid && (
              <div className="mt-2 font-mono text-[10px] text-stone-400 break-all">
                UUID: {promo.external_uuid}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {!isEdit && (
              <button
                type="button"
                onClick={() => setIsEdit(true)}
                aria-label="Edit"
                className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        <div>
          {/* Fields block (view/edit) */}
          <div className="px-5 py-4 border-b border-stone-200 space-y-3">
            <div>
              <label className={lCls}>Код</label>
              {isEdit ? (
                <Input
                  className="font-mono uppercase"
                  value={form.code}
                  onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                  aria-label="Код"
                />
              ) : (
                <div className="font-mono text-xs text-stone-900 break-all">{form.code}</div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                {isEdit ? (
                  <SelectMenu
                    label="Канал"
                    value={form.channel}
                    placeholder="Выбрать…"
                    options={channels.map((c) => ({ value: c.slug, label: c.label }))}
                    onChange={(v) => setForm((f) => ({ ...f, channel: v }))}
                    allowAdd
                  />
                ) : (
                  <div>
                    <div className={lCls}>Канал</div>
                    <div className="text-sm text-stone-900">{form.channel || '—'}</div>
                  </div>
                )}
              </div>
              <div>
                <label className={lCls}>Скидка %</label>
                {isEdit ? (
                  <Input
                    type="number"
                    value={form.discount_pct}
                    onChange={(e) => setForm((f) => ({ ...f, discount_pct: e.target.value }))}
                    aria-label="Скидка %"
                  />
                ) : (
                  <div className="text-sm tabular-nums text-stone-900">
                    {form.discount_pct ? `${form.discount_pct}%` : '—'}
                  </div>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={lCls}>Начало</label>
                {isEdit ? (
                  <Input
                    type="date"
                    value={form.valid_from}
                    onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
                    aria-label="Начало"
                  />
                ) : (
                  <div className="text-sm tabular-nums text-stone-900">{form.valid_from || '—'}</div>
                )}
              </div>
              <div>
                <label className={lCls}>Окончание</label>
                {isEdit ? (
                  <Input
                    type="date"
                    value={form.valid_until}
                    onChange={(e) => setForm((f) => ({ ...f, valid_until: e.target.value }))}
                    aria-label="Окончание"
                  />
                ) : (
                  <div className="text-sm tabular-nums text-stone-900">{form.valid_until || '—'}</div>
                )}
              </div>
            </div>
            {isEdit && (
              <div className="flex gap-2 pt-1">
                <Button onClick={handleSave} disabled={updateMut.isPending} className="flex-1">
                  {updateMut.isPending ? 'Сохраняю…' : 'Сохранить'}
                </Button>
                <Button variant="secondary" onClick={handleCancel}>
                  Отмена
                </Button>
              </div>
            )}
          </div>

          {/* KPI block */}
          <div className="px-5 py-4 border-b border-stone-200">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, шт</div>
                <div className="text-lg font-medium text-stone-900 tabular-nums">{fmt(qty)}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, ₽</div>
                <div className="text-lg font-medium text-stone-900 tabular-nums">{fmtR(sales)}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Ср. чек, ₽</div>
                <div className="text-lg font-medium text-stone-900 tabular-nums">{avg > 0 ? fmtR(avg) : '—'}</div>
              </div>
            </div>
          </div>

          {/* Weekly stats */}
          <div className="px-5 py-4 border-b border-stone-200">
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">По неделям</div>
            {weeklyLoading ? (
              <div className="text-sm text-stone-500">Загрузка…</div>
            ) : weeklyError ? (
              <EmptyState title="Ошибка загрузки" description="Не удалось загрузить данные по неделям." />
            ) : weekly.length === 0 ? (
              <EmptyState title="По неделям" description="Данные появятся после понедельника." />
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-100">
                    <th className="text-left py-1 text-[10px] uppercase text-stone-400 font-medium">Нед</th>
                    <th className="text-right py-1 text-[10px] uppercase text-stone-400 font-medium">Зак.</th>
                    <th className="text-right py-1 text-[10px] uppercase text-stone-400 font-medium">Продажи</th>
                    <th className="text-right py-1 text-[10px] uppercase text-stone-400 font-medium">Возвр.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-50">
                  {weekly.map((w) => (
                    <tr key={w.week_start}>
                      <td className="py-1.5 tabular-nums text-stone-500">{w.week_start}</td>
                      <td className="py-1.5 text-right tabular-nums text-stone-900 font-medium">{w.orders_count}</td>
                      <td className="py-1.5 text-right tabular-nums text-stone-700">{fmtR(w.sales_rub)}</td>
                      <td className="py-1.5 text-right tabular-nums text-stone-400">{w.returns_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Product breakdown — aggregated by SKU across all weeks */}
          <div className="px-5 py-4">
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">Товарная разбивка</div>
            {breakdownLoading ? (
              <div className="text-sm text-stone-500">Загрузка…</div>
            ) : breakdownError ? (
              <EmptyState title="Ошибка загрузки" description="Не удалось загрузить товарную разбивку." />
            ) : breakdownAgg.length === 0 ? (
              <EmptyState title="Товарная разбивка" description="Данные собираются" />
            ) : (
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-stone-100">
                    <th className="text-left py-1 text-[10px] uppercase text-stone-400 font-medium">Товар</th>
                    <th className="text-right py-1 text-[10px] uppercase text-stone-400 font-medium">Шт</th>
                    <th className="text-right py-1 text-[10px] uppercase text-stone-400 font-medium">Сумма</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-50">
                  {breakdownAgg.map((p) => (
                    <tr key={p.sku_label}>
                      <td className="py-1.5">
                        <div className="font-mono text-stone-900 break-all">{p.sku_label}</div>
                        {p.model_code && (
                          <div className="text-[10px] text-stone-400">{p.model_code}</div>
                        )}
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-stone-700">{fmt(p.qty)}</td>
                      <td className="py-1.5 text-right tabular-nums text-stone-900 font-medium">{fmtR(p.amount_rub)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    )
  )

  return (
    <Drawer open={true} onClose={onClose} title={promo?.code ?? 'Промокод'} width="lg">
      {body}
    </Drawer>
  )
}
