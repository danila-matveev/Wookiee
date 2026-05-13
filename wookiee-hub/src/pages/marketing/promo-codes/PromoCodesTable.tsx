import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Search } from "lucide-react"
import { usePromoCodes, usePromoStatsWeekly } from "@/hooks/marketing/use-promo-codes"
import { useChannelLabelLookup } from "@/hooks/marketing/use-channels"
import { useGroupByPref } from "@/hooks/marketing/use-group-by-pref"
import { QueryStatusBoundary } from "@/components/crm/ui/QueryStatusBoundary"
import { Badge } from "@/components/marketing/Badge"
import { SectionHeader } from "@/components/marketing/SectionHeader"
import { GroupBySelector } from "@/components/marketing/GroupBySelector"
import { DateRange } from "@/components/marketing/DateRange"
import { UpdateBar } from "@/components/marketing/UpdateBar"
import { KpiCard } from "@/components/marketing/KpiCard"
import type { PromoCodeRow } from "@/types/marketing"

const FIRST = '2025-07-28'
const LAST  = new Date().toISOString().slice(0, 10)

type PromoGroupBy = "channel" | "status" | "none"

const PROMO_GROUP_BY_OPTIONS = [
  { value: "channel" as const, label: "По каналу" },
  { value: "status" as const,  label: "По статусу" },
  { value: "none" as const,    label: "Без группировки" },
] as const

type EnrichedPromo = PromoCodeRow & { qty: number; sales: number }

function getPromoStatusLabel(p: Pick<EnrichedPromo, 'status' | 'qty'>): string {
  if (p.status === 'expired')  return 'Истёк'
  if (p.status === 'archived') return 'Архив'
  if (p.status === 'paused')   return 'На паузе'
  if (p.qty === 0)             return 'Нет данных'
  return 'Активен'
}

export function PromoCodesTable() {
  const [params, setParams] = useSearchParams()
  const search   = params.get('q') ?? ''
  const dateFrom = params.get('from') ?? '2026-03-30'
  const dateTo   = params.get('to')   ?? LAST

  const { data: promos = [], isLoading: lp, error: ep } = usePromoCodes()
  const { data: weekly = [], isLoading: lw, error: ew } = usePromoStatsWeekly()
  const channelLabel = useChannelLabelLookup()

  const { value: groupBy, setValue: setGroupBy } = useGroupByPref<PromoGroupBy>('marketing.promo-codes', 'channel')
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const toggle = (k: string) => setCollapsed((c) => ({ ...c, [k]: !c[k] }))

  const enriched = useMemo(() => {
    const inRange = weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo)
    const byId = new Map<number, { qty: number; sales: number }>()
    for (const w of inRange) {
      const cur = byId.get(w.promo_code_id) ?? { qty: 0, sales: 0 }
      cur.qty   += w.orders_count
      cur.sales += w.sales_rub
      byId.set(w.promo_code_id, cur)
    }
    return promos.map((p) => ({ ...p, qty: byId.get(p.id)?.qty ?? 0, sales: byId.get(p.id)?.sales ?? 0 }))
  }, [promos, weekly, dateFrom, dateTo])

  const filtered = useMemo(() => {
    let l = enriched
    if (search) {
      const q = search.toLowerCase()
      l = l.filter((p) =>
        p.code.toLowerCase().includes(q)
        || p.channel?.toLowerCase().includes(q)
        || channelLabel(p.channel).toLowerCase().includes(q),
      )
    }
    return l.sort((a, b) => b.sales - a.sales)
  }, [enriched, search, channelLabel])

  const totals = useMemo(() => ({
    qty:   filtered.reduce((s, p) => s + p.qty, 0),
    sales: filtered.reduce((s, p) => s + p.sales, 0),
  }), [filtered])

  const grouped = useMemo(() => {
    if (groupBy === 'none') {
      return [{ key: '_all', label: '', items: filtered }]
    }
    const map = new Map<string, EnrichedPromo[]>()
    for (const p of filtered) {
      const key = groupBy === 'channel'
        ? (p.channel ?? '_no_channel')
        : getPromoStatusLabel(p)
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(p)
    }
    return Array.from(map.entries())
      .map(([key, items]) => {
        const label = groupBy === 'channel'
          ? (key === '_no_channel' ? 'Без канала' : channelLabel(key))
          : key
        return { key, label, items }
      })
      .sort((a, b) => a.label.localeCompare(b.label, 'ru'))
  }, [filtered, groupBy, channelLabel])

  const setQ = (k: string, v: string | null) => setParams((p) => { v ? p.set(k, v) : p.delete(k); return p })

  return (
    <QueryStatusBoundary isLoading={lp || lw} error={ep ?? ew}>
      <div className="grid grid-cols-4 gap-3 px-6 py-4 border-b border-border">
        <KpiCard label="Активных" value={String(promos.filter((p) => p.status === 'active').length)} sub={`из ${promos.length}`} />
        <KpiCard label="Продажи, шт" value={fmt(totals.qty)} />
        <KpiCard label="Продажи, ₽" value={fmtR(totals.sales)} />
        <KpiCard label="Ср. чек, ₽" value={totals.qty > 0 ? fmtR(Math.round(totals.sales / totals.qty)) : '—'} />
      </div>

      <UpdateBar job="promocodes" />

      <div className="px-6 py-2 border-b border-border flex items-center gap-3 bg-card flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" aria-hidden />
          <input
            value={search} onChange={(e) => setQ('q', e.target.value || null)}
            placeholder="Код или канал…"
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-border rounded-md bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label="Поиск промокода"
          />
        </div>
        <DateRange from={dateFrom} to={dateTo} min={FIRST} max={LAST} onChange={(f, t) => setParams((p) => { p.set('from', f); p.set('to', t); return p })} />
        <GroupBySelector value={groupBy} options={PROMO_GROUP_BY_OPTIONS} onChange={setGroupBy} />
        <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">{filtered.length} кодов</span>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full table-fixed">
          <colgroup>
            <col className="w-[220px]" /><col className="w-[120px]" /><col className="w-[80px]" /><col className="w-[110px]" />
            <col /><col /><col />
          </colgroup>
          <thead className="sticky top-0 bg-muted/95 backdrop-blur-sm border-b border-border z-10">
            <tr>
              {['Код','Канал','Скидка','Статус'].map((h) => <th key={h} className={TH}>{h}</th>)}
              {['Продажи, шт','Продажи, ₽','Ср. чек, ₽'].map((h) => <th key={h} className={THR}>{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {grouped.map((g) => {
              const hideHeader = groupBy === 'none'
              const isCol = !hideHeader && !!collapsed[g.key]
              return (
                <PromoSectionGroup
                  key={g.key}
                  label={g.label}
                  rows={g.items}
                  collapsed={isCol}
                  hideHeader={hideHeader}
                  onToggle={() => toggle(g.key)}
                  channelLabel={channelLabel}
                  onOpen={(id) => setQ('open', String(id))}
                />
              )
            })}
          </tbody>
          <tfoot className="sticky bottom-0 bg-muted/95 backdrop-blur-sm border-t-2 border-border z-10">
            <tr>
              <td className="px-2 py-2 text-xs font-medium text-foreground" colSpan={4}>Итого · {filtered.length} кодов</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmt(totals.qty)}</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmtR(totals.sales)}</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground/80">{totals.qty > 0 ? fmtR(Math.round(totals.sales / totals.qty)) : '—'}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </QueryStatusBoundary>
  )
}

const TH  = "px-2 py-2 text-left  text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const THR = "px-2 py-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const fmt  = (n: number) => n.toLocaleString('ru-RU')
const fmtR = (n: number) => `${n.toLocaleString('ru-RU')} ₽`

interface PromoSectionGroupProps {
  label: string
  rows: EnrichedPromo[]
  collapsed: boolean
  hideHeader: boolean
  onToggle: () => void
  channelLabel: (slug: string | null | undefined) => string
  onOpen: (id: number) => void
}

function PromoSectionGroup({ label, rows, collapsed, hideHeader, onToggle, channelLabel, onOpen }: PromoSectionGroupProps) {
  const showRows = hideHeader || !collapsed
  return (
    <>
      {!hideHeader && (
        <SectionHeader icon="" label={label} count={rows.length} collapsed={collapsed} onToggle={onToggle} colSpan={7} />
      )}
      {showRows && rows.length === 0 && (
        <tr>
          <td colSpan={7} className="px-3 py-6 text-center text-[11px] text-muted-foreground">Нет данных</td>
        </tr>
      )}
      {showRows && rows.map((p) => {
        const color: 'amber' | 'gray' | 'blue' | 'green' =
          p.status === 'expired'  ? 'amber' :
          p.status === 'archived' ? 'gray'  :
          p.status === 'paused'   ? 'blue'  :
          p.qty === 0             ? 'gray'  : 'green'
        const lab  = p.status === 'expired' ? 'Истёк' : p.status === 'archived' ? 'Архив' : p.status === 'paused' ? 'На паузе' : p.qty === 0 ? 'Нет данных' : 'Активен'
        const avg  = p.qty > 0 ? Math.round(p.sales / p.qty) : 0
        return (
          <tr key={p.id}
              tabIndex={0}
              onClick={() => onOpen(p.id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(p.id) } }}
              className="cursor-pointer transition-colors hover:bg-muted/50 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-inset">
            <td className="px-2 py-2.5"><span className="font-mono text-xs text-foreground">{p.code.length > 24 ? p.code.slice(0, 24) + '…' : p.code}</span></td>
            <td className="px-2 py-2.5"><Badge color="gray" label={channelLabel(p.channel)} compact /></td>
            <td className="px-2 py-2.5 text-sm tabular-nums text-foreground/80">{p.discount_pct != null ? `${p.discount_pct}%` : '—'}</td>
            <td className="px-2 py-2.5"><Badge color={color} label={lab} compact /></td>
            <td className="px-2 py-2.5 text-right tabular-nums text-sm font-medium text-foreground">{p.qty > 0 ? fmt(p.qty) : <span className="text-muted-foreground/50">—</span>}</td>
            <td className="px-2 py-2.5 text-right tabular-nums text-sm text-foreground/80">{p.sales > 0 ? fmtR(p.sales) : <span className="text-muted-foreground/50">—</span>}</td>
            <td className="px-2 py-2.5 text-right tabular-nums text-sm text-muted-foreground">{avg > 0 ? fmtR(avg) : <span className="text-muted-foreground/50">—</span>}</td>
          </tr>
        )
      })}
    </>
  )
}
