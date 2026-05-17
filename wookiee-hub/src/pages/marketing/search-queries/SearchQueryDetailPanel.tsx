import { useMemo, useState } from "react"
import { Drawer } from "@/components/crm/ui/Drawer"
import { Badge } from "@/components/marketing/Badge"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import { StatusEditor } from "@/components/marketing/StatusEditor"
import { useSearchQueries, useSearchQueryWeeklyByWord, useUpdateSearchQueryStatus, useSearchQueryProductBreakdown } from "@/hooks/marketing/use-search-queries"
import type { SearchQueryRow, SearchQueryWeeklyStat, SearchQueryProductBreakdownAgg, StatusUI } from "@/types/marketing"
import { STATUS_DB_TO_UI } from "@/types/marketing"

interface SearchQueryDetailPanelProps {
  unifiedId: string
  dateFrom: string
  dateTo: string
  onClose: () => void
}

const fmt = (n: number) => n.toLocaleString('ru-RU')
const pct = (num: number, denom: number) => (denom > 0 ? `${((num / denom) * 100).toFixed(1)}%` : '—')
const fmtWeek = (iso: string) => {
  // Robust DD.MM formatter that doesn't depend on Intl locale data in jsdom.
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (m) return `${m[3]}.${m[2]}`
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${dd}.${mm}`
}

export function SearchQueryDetailPanel({ unifiedId, dateFrom, dateTo, onClose }: SearchQueryDetailPanelProps) {
  const { data: items = [], isLoading: itemsLoading } = useSearchQueries()
  const item: SearchQueryRow | undefined = items.find((i) => i.unified_id === unifiedId)
  const updateStatus = useUpdateSearchQueryStatus()

  // Unified weekly source: same JOIN key as RPC v3
  // (search_word = query_text OR nomenklatura_wb) — works for brands,
  // nm_id substitutes and WW-codes alike, no entity_type branching needed.
  const searchWord = item?.query_text ?? null
  const nomenklaturaWb = item?.nomenklatura_wb ?? null

  const { data: weekly = [], isLoading: weeklyLoading, error: weeklyError } =
    useSearchQueryWeeklyByWord(searchWord, nomenklaturaWb)

  // Per-product breakdown — какие WB-карточки открывали/покупали в результате этого запроса/WW-кода.
  // Источник: marketing.search_query_product_breakdown (search_word matches query_text).
  const { data: breakdownRows = [], isLoading: breakdownLoading } =
    useSearchQueryProductBreakdown(item?.query_text ?? null, dateFrom, dateTo)

  const breakdownAgg: SearchQueryProductBreakdownAgg[] = useMemo(() => {
    if (breakdownRows.length === 0) return []
    const map = new Map<number, SearchQueryProductBreakdownAgg>()
    for (const r of breakdownRows) {
      const cur = map.get(r.nm_id) ?? {
        nm_id: r.nm_id,
        sku_label: r.sku_label,
        model_code: r.model_code,
        open_card: 0,
        add_to_cart: 0,
        orders: 0,
      }
      cur.open_card += r.open_card
      cur.add_to_cart += r.add_to_cart
      cur.orders += r.orders
      map.set(r.nm_id, cur)
    }
    return Array.from(map.values()).sort((a, b) => b.orders - a.orders || b.open_card - a.open_card)
  }, [breakdownRows])

  const [weeklyMode, setWeeklyMode] = useState<'period' | 'all'>('period')
  const rangeWeeks = useMemo(
    () => weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo),
    [weekly, dateFrom, dateTo],
  )
  const sliced = weeklyMode === 'all' ? weekly : rangeWeeks
  const total    = useMemo(() => aggregate(rangeWeeks), [rangeWeeks])
  const allTotal = useMemo(() => aggregate(weekly), [weekly])

  const body = (
    itemsLoading ? (
      <div className="text-sm text-muted-foreground p-4">Загрузка…</div>
    ) : !item ? (
      <EmptyState title="Запрос не найден" description="Возможно, он удалён или ID неверен." />
    ) : (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 flex-wrap">
          <StatusEditor
            status={STATUS_DB_TO_UI[item.status] ?? 'archive'}
            onChange={(next: StatusUI) =>
              updateStatus.mutate({ unifiedId: item.unified_id, status: next })
            }
          />
          {updateStatus.isError && (
            <span className="text-xs text-danger">Не удалось сохранить статус</span>
          )}
          {(item.channel_label || item.purpose) && (
            <Badge color="gray" label={(item.channel_label || item.purpose)!} compact />
          )}
          {item.campaign_name && <Badge color="blue" label={item.campaign_name} compact />}
        </div>

        {(item.nomenklatura_wb || item.ww_code || item.sku_label || item.artikul_id != null || item.model_hint) && (
          <div className="bg-muted/30 rounded-md border border-border px-3 py-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
            {item.nomenklatura_wb && (
              <>
                <span className="text-muted-foreground">Номенклатура</span>
                <span className="font-mono text-foreground/80 text-right">{item.nomenklatura_wb}</span>
              </>
            )}
            {item.ww_code && (
              <>
                <span className="text-muted-foreground">WW-код</span>
                <span className="font-mono text-foreground/80 text-right">{item.ww_code}</span>
              </>
            )}
            {item.sku_label ? (
              <>
                <span className="text-muted-foreground">Артикул</span>
                <span className="font-mono text-foreground/80 text-right">{item.sku_label}</span>
              </>
            ) : item.artikul_id != null && (
              <>
                <span className="text-muted-foreground">Артикул ID</span>
                <span className="text-foreground/80 text-right">{item.artikul_id}</span>
              </>
            )}
            {item.model_hint && (
              <>
                <span className="text-muted-foreground">Модель</span>
                <span className="text-foreground/80 text-right">{item.model_hint}</span>
              </>
            )}
          </div>
        )}

        <div className="border-t border-stone-200 pt-3" data-testid="funnel-block">
          <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">За выбранный период</div>
          <div className="space-y-2">
            <Row label="Частота"  value={fmt(total.f)} />
            <Row label="Переходы" value={fmt(total.t)} />
            <SubRow label="CR перех → корзина" value={pct(total.a, total.t)} />
            <Row label="Корзина" value={fmt(total.a)} />
            <SubRow label="CR корзина → заказ" value={pct(total.o, total.a)} />
            <Row label="Заказы"  value={fmt(total.o)} />
            <div className="pt-1 mt-1 border-t border-stone-100 flex items-center justify-between">
              <span className="text-xs font-medium text-stone-700">CR перех → заказ</span>
              <span className="text-sm font-medium text-stone-900 tabular-nums">{pct(total.o, total.t)}</span>
            </div>
          </div>
          <div className="text-[10px] text-stone-400 mt-3">
            Всего за всё время: {fmt(allTotal.o)} заказов · {weekly.length} нед данных
          </div>
        </div>

        <div className="border-t border-stone-200 pt-3" data-testid="weekly-block">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase tracking-wider text-stone-400">По неделям</span>
            <div className="inline-flex items-center gap-1" role="tablist" aria-label="Период недельной статистики">
              <button
                type="button"
                role="tab"
                aria-selected={weeklyMode === 'period'}
                onClick={() => setWeeklyMode('period')}
                className={
                  'px-2 py-0.5 rounded-md text-[11px] transition-colors ' +
                  (weeklyMode === 'period'
                    ? 'bg-stone-100 text-stone-900 font-medium'
                    : 'text-stone-500 hover:bg-stone-50 hover:text-stone-700')
                }
              >
                За период {rangeWeeks.length > 0 && <span className="text-stone-400">({rangeWeeks.length})</span>}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={weeklyMode === 'all'}
                onClick={() => setWeeklyMode('all')}
                className={
                  'px-2 py-0.5 rounded-md text-[11px] transition-colors ' +
                  (weeklyMode === 'all'
                    ? 'bg-stone-100 text-stone-900 font-medium'
                    : 'text-stone-500 hover:bg-stone-50 hover:text-stone-700')
                }
              >
                Все {weekly.length > 0 && <span className="text-stone-400">({weekly.length})</span>}
              </button>
            </div>
          </div>
          {weeklyLoading ? (
            <div className="text-sm text-muted-foreground">Загрузка…</div>
          ) : weeklyError ? (
            <>
              {(() => { console.error('[SearchQueryDetailPanel] weekly load error', weeklyError); return null })()}
              <EmptyState title="Ошибка загрузки" description="Не удалось загрузить недельную статистику." />
            </>
          ) : sliced.length === 0 ? (
            <div className="py-6 flex flex-col items-center gap-2">
              <p className="text-xs text-stone-400 italic">
                {weeklyMode === 'period' ? 'Нет данных за этот период' : 'Нет данных'}
              </p>
            </div>
          ) : (
            <div className="overflow-y-auto max-h-[280px]">
              <table className="w-full text-xs" aria-label="Недельная статистика">
                <thead className="sticky top-0 bg-stone-50/90 backdrop-blur-sm">
                  <tr className="border-b border-stone-200">
                    <th className="px-1 py-1 text-left  text-[10px] uppercase text-stone-400 font-medium">Нед</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Част.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Перех.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Корз.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Зак.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">CRV</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-50">
                  {sliced.map((w) => (
                    <tr key={w.week_start} className="hover:bg-stone-50/60">
                      <td className="px-1 py-1 tabular-nums text-stone-500">{fmtWeek(w.week_start)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-600">{fmt(w.frequency)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.transitions)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.additions)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-900 font-medium">{fmt(w.orders)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-400">{pct(w.orders, w.transitions)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* По товарам — какие WB карточки открывали/покупали по этому запросу */}
        <div className="border-t border-stone-200 pt-3" data-testid="product-breakdown-block">
          <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">
            По товарам (за выбранный период)
          </div>
          {breakdownLoading ? (
            <div className="text-sm text-muted-foreground">Загрузка…</div>
          ) : breakdownAgg.length === 0 ? (
            <div className="py-3 text-xs text-stone-400 italic">Нет данных за этот период</div>
          ) : (
            <div className="overflow-y-auto max-h-[320px]">
              <table className="w-full text-xs" aria-label="Разбивка по товарам">
                <thead className="sticky top-0 bg-stone-50/90 backdrop-blur-sm">
                  <tr className="border-b border-stone-200">
                    <th className="px-1 py-1 text-left  text-[10px] uppercase text-stone-400 font-medium">Артикул</th>
                    <th className="px-1 py-1 text-left  text-[10px] uppercase text-stone-400 font-medium">Модель</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Откр.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Корз.</th>
                    <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400 font-medium">Зак.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-50">
                  {breakdownAgg.map((p) => (
                    <tr key={p.nm_id} className="hover:bg-stone-50/60">
                      <td className="px-1 py-1 truncate text-stone-700" title={p.sku_label}>{p.sku_label}</td>
                      <td className="px-1 py-1 text-stone-500">{p.model_code ?? '—'}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-600">{fmt(p.open_card)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(p.add_to_cart)}</td>
                      <td className="px-1 py-1 text-right tabular-nums text-stone-900 font-medium">{fmt(p.orders)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="sticky bottom-0 bg-stone-50/90 backdrop-blur-sm">
                  <tr className="border-t border-stone-200">
                    <td colSpan={2} className="px-1 py-1 text-[10px] text-stone-400">Итого по {breakdownAgg.length} товарам</td>
                    <td className="px-1 py-1 text-right tabular-nums text-[11px] text-stone-600">{fmt(breakdownAgg.reduce((s, r) => s + r.open_card, 0))}</td>
                    <td className="px-1 py-1 text-right tabular-nums text-[11px] text-stone-500">{fmt(breakdownAgg.reduce((s, r) => s + r.add_to_cart, 0))}</td>
                    <td className="px-1 py-1 text-right tabular-nums text-[11px] font-medium text-stone-900">{fmt(breakdownAgg.reduce((s, r) => s + r.orders, 0))}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </div>
    )
  )

  return (
    <Drawer open={true} onClose={onClose} title={item?.query_text ?? 'Запрос'} width="lg">
      {body}
    </Drawer>
  )
}

interface RowProps { label: string; value: string }
function Row({ label, value }: RowProps) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-stone-500">{label}</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{value}</span>
    </div>
  )
}

function SubRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between pl-4 -mt-0.5">
      <span className="text-[11px] text-stone-400">{label}</span>
      <span className="text-[11px] text-stone-500 tabular-nums">{value}</span>
    </div>
  )
}

function aggregate(rows: SearchQueryWeeklyStat[]) {
  return rows.reduce(
    (acc, r) => ({
      f: acc.f + r.frequency,
      t: acc.t + r.transitions,
      a: acc.a + r.additions,
      o: acc.o + r.orders,
    }),
    { f: 0, t: 0, a: 0, o: 0 },
  )
}
