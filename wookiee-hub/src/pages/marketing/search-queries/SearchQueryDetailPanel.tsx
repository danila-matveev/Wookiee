import { useMemo, useState } from "react"
import { Drawer } from "@/components/crm/ui/Drawer"
import { Badge } from "@/components/crm/ui/Badge"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import { StatusEditor } from "@/components/marketing/StatusEditor"
import { useSearchQueries, useSearchQueryWeekly } from "@/hooks/marketing/use-search-queries"
import { parseUnifiedId } from "@/lib/marketing-helpers"
import type { SearchQueryRow, SearchQueryWeeklyStat } from "@/types/marketing"

interface SearchQueryDetailPanelProps {
  unifiedId: string
  dateFrom: string
  dateTo: string
  onClose: () => void
}

const fmt = (n: number) => n.toLocaleString('ru-RU')
const pct = (num: number, denom: number) => (denom > 0 ? `${((num / denom) * 100).toFixed(1)}%` : '—')
const lCls = "block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1"

export function SearchQueryDetailPanel({ unifiedId, dateFrom, dateTo, onClose }: SearchQueryDetailPanelProps) {
  const { data: items = [], isLoading: itemsLoading } = useSearchQueries()
  const item: SearchQueryRow | undefined = items.find((i) => i.unified_id === unifiedId)

  let parsed: { source: 'branded_queries' | 'substitute_articles'; id: number } | null = null
  try { parsed = parseUnifiedId(unifiedId) } catch { parsed = null }

  const isSubstitute = parsed?.source === 'substitute_articles'
  const substituteId = isSubstitute ? parsed!.id : null

  const { data: weekly = [], isLoading: weeklyLoading, error: weeklyError } = useSearchQueryWeekly(substituteId)

  const [showAll, setShowAll] = useState(false)
  const rangeWeeks = useMemo(
    () => weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo),
    [weekly, dateFrom, dateTo],
  )
  const sliced = showAll ? weekly : rangeWeeks
  const total    = useMemo(() => aggregate(rangeWeeks), [rangeWeeks])
  const allTotal = useMemo(() => aggregate(weekly), [weekly])

  return (
    <Drawer open={true} onClose={onClose} title={item?.query_text ?? 'Запрос'}>
      {itemsLoading ? (
        <div className="text-sm text-muted-foreground p-4">Загрузка…</div>
      ) : !item ? (
        <EmptyState title="Запрос не найден" description="Возможно, он удалён или ID неверен." />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-1.5 flex-wrap">
            <StatusEditor status={item.status} onChange={() => {}} disabled />
            {item.purpose && <Badge tone="secondary">{item.purpose}</Badge>}
            {item.campaign_name && <Badge tone="info">{item.campaign_name}</Badge>}
          </div>

          {(item.nomenklatura_wb || item.ww_code || item.artikul_id != null || item.model_hint) && (
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
              {item.artikul_id != null && (
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

          <div className="border-t border-border pt-3">
            <span className={lCls}>За выбранный период</span>
            <div className="space-y-2">
              <Row label="Частота"  value={fmt(total.f)} />
              <Row label="Переходы" value={fmt(total.t)} />
              <SubRow label="CR Перех→корз" value={pct(total.a, total.t)} />
              <Row label="Корзина" value={fmt(total.a)} />
              <SubRow label="CR Корз→Зак" value={pct(total.o, total.a)} />
              <Row label="Заказы"  value={fmt(total.o)} bold />
              <div className="pt-1 mt-1 border-t border-border/50 flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">CR Перех→Зак</span>
                <span className="text-sm font-medium text-foreground tabular-nums">{pct(total.o, total.t)}</span>
              </div>
            </div>
            <div className="text-[10px] text-muted-foreground mt-3">
              Всего за всё время: {fmt(allTotal.o)} заказов · {weekly.length} нед данных
            </div>
          </div>

          <div className="border-t border-border pt-3">
            <div className="flex items-center justify-between mb-2">
              <span className={lCls + ' mb-0'}>{showAll ? 'Все недели' : 'За период'}</span>
              {weekly.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowAll((s) => !s)}
                  className="text-[11px] text-muted-foreground hover:text-foreground underline"
                >
                  {showAll ? `За период (${rangeWeeks.length})` : `Все ${weekly.length}`}
                </button>
              )}
            </div>
            {!isSubstitute ? (
              <EmptyState title="По неделям" description="Недельная статистика для брендовых запросов появится в Phase 2." />
            ) : weeklyLoading ? (
              <div className="text-sm text-muted-foreground">Загрузка…</div>
            ) : weeklyError ? (
              <>
                {(() => { console.error('[SearchQueryDetailPanel] weekly load error', weeklyError); return null })()}
                <EmptyState title="Ошибка загрузки" description="Не удалось загрузить недельную статистику." />
              </>
            ) : sliced.length === 0 ? (
              <EmptyState title="По неделям" description="Нет данных за выбранный период." />
            ) : (
              <div className="overflow-y-auto max-h-[280px]">
                <table className="w-full text-xs" aria-label="Недельная статистика">
                  <thead className="sticky top-0 bg-muted/95 backdrop-blur-sm">
                    <tr className="border-b border-border">
                      <th className="px-1 py-1 text-left  text-[10px] uppercase text-muted-foreground font-medium">Нед</th>
                      <th className="px-1 py-1 text-right text-[10px] uppercase text-muted-foreground font-medium">Част.</th>
                      <th className="px-1 py-1 text-right text-[10px] uppercase text-muted-foreground font-medium">Перех.</th>
                      <th className="px-1 py-1 text-right text-[10px] uppercase text-muted-foreground font-medium">Корз.</th>
                      <th className="px-1 py-1 text-right text-[10px] uppercase text-muted-foreground font-medium">Зак.</th>
                      <th className="px-1 py-1 text-right text-[10px] uppercase text-muted-foreground font-medium">CRV</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {sliced.map((w) => (
                      <tr key={w.week_start} className="hover:bg-muted/40">
                        <td className="px-1 py-1 tabular-nums text-muted-foreground">{w.week_start}</td>
                        <td className="px-1 py-1 text-right tabular-nums text-foreground/80">{fmt(w.frequency)}</td>
                        <td className="px-1 py-1 text-right tabular-nums text-foreground/80">{fmt(w.transitions)}</td>
                        <td className="px-1 py-1 text-right tabular-nums text-foreground/80">{fmt(w.additions)}</td>
                        <td className="px-1 py-1 text-right tabular-nums text-foreground font-medium">{fmt(w.orders)}</td>
                        <td className="px-1 py-1 text-right tabular-nums text-muted-foreground">{pct(w.orders, w.transitions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  )
}

interface RowProps { label: string; value: string; bold?: boolean }
function Row({ label, value, bold }: RowProps) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-sm tabular-nums ${bold ? 'font-semibold text-foreground' : 'font-medium text-foreground'}`}>{value}</span>
    </div>
  )
}

function SubRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between pl-4 !-mt-1.5">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[11px] text-muted-foreground tabular-nums">{value}</span>
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
