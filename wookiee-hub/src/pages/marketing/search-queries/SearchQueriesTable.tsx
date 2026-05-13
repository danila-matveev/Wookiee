import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Search } from "lucide-react"
import { useSearchQueries, useSearchQueryStats } from "@/hooks/marketing/use-search-queries"
import { useChannelLabelLookup } from "@/hooks/marketing/use-channels"
import { useGroupByPref } from "@/hooks/marketing/use-group-by-pref"
import { QueryStatusBoundary } from "@/components/crm/ui/QueryStatusBoundary"
import { Badge } from "@/components/marketing/Badge"
import { SectionHeader } from "@/components/marketing/SectionHeader"
import { GroupBySelector } from "@/components/marketing/GroupBySelector"
import { DateRange } from "@/components/marketing/DateRange"
import { UpdateBar } from "@/components/marketing/UpdateBar"
import type { SearchQueryRow, SearchQueryStatsAgg } from "@/types/marketing"

const FIRST = '2025-07-28'
const LAST  = new Date().toISOString().slice(0, 10)

type SqGroupBy = "direction" | "entity_type" | "none"

const SQ_GROUP_BY_OPTIONS = [
  { value: "direction" as const,   label: "По направлению" },
  { value: "entity_type" as const, label: "По типу сущности" },
  { value: "none" as const,        label: "Без группировки" },
] as const

const GROUP_LABELS_DIRECTION: Record<string, { icon: string; label: string }> = {
  brand:       { icon: "🔤", label: "Брендированные запросы" },
  external:    { icon: "📦", label: "Артикулы (внешний лид)" },
  cr_general:  { icon: "👥", label: "Креаторы общие" },
  cr_personal: { icon: "👤", label: "Креаторы личные" },
}

const GROUP_LABELS_ENTITY: Record<string, { icon: string; label: string }> = {
  brand:        { icon: "🔤", label: "Брендированные запросы" },
  nomenclature: { icon: "🏷️", label: "Номенклатуры" },
  ww_code:      { icon: "🔗", label: "Подменные артикулы" },
  other:        { icon: "❔", label: "Прочее" },
}

function getGroupKey(row: SearchQueryRow, mode: SqGroupBy): string {
  if (mode === "direction") return row.group_kind ?? "external"
  if (mode === "entity_type") {
    // entity_type is added by view v2 (Phase 2B). Until then derive from row shape.
    const entityType = (row as unknown as { entity_type?: string }).entity_type
    if (entityType) return entityType
    if (row.group_kind === "brand") return "brand"
    if (row.ww_code) return "ww_code"
    if (row.nomenklatura_wb) return "nomenclature"
    return "other"
  }
  return "_all"
}

const TH  = "px-2 py-2 text-left  text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const THR = "px-2 py-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const fmt = (n: number) => n.toLocaleString('ru-RU')
const pct = (num: number, denom: number) => (denom > 0 ? `${((num / denom) * 100).toFixed(1)}%` : '')

const ZERO_STATS: SearchQueryStatsAgg = {
  unified_id: '',
  frequency: 0,
  transitions: 0,
  additions: 0,
  orders: 0,
}

export function SearchQueriesTable() {
  const [params, setParams] = useSearchParams()
  const search   = params.get('q')       ?? ''
  const modelF   = params.get('model')   ?? 'all'
  const channelF = params.get('channel') ?? 'all'
  const dateFrom = params.get('from')    ?? '2026-03-30'
  const dateTo   = params.get('to')      ?? LAST

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const toggle = (g: string) => setCollapsed((c) => ({ ...c, [g]: !c[g] }))

  const { value: groupBy, setValue: setGroupBy } = useGroupByPref<SqGroupBy>('marketing.search-queries', 'direction')

  const { data: items = [], isLoading: lq, error: eq } = useSearchQueries()
  const { data: statsRows = [], isLoading: ls, error: es } = useSearchQueryStats(dateFrom, dateTo)
  const channelLabel = useChannelLabelLookup()

  const statsMap = useMemo(() => {
    const m = new Map<string, SearchQueryStatsAgg>()
    for (const s of statsRows) m.set(s.unified_id, s)
    return m
  }, [statsRows])

  const setQ = (k: string, v: string | null) => setParams((p) => { v ? p.set(k, v) : p.delete(k); return p })

  const uniqueModels = useMemo(
    () => Array.from(new Set(items.map((i) => i.model_hint).filter((m): m is string => !!m))).sort(),
    [items],
  )
  const uniqueChannels = useMemo(
    () => Array.from(new Set(items.map((i) => i.purpose).filter((c): c is string => !!c)))
      .sort((a, b) => channelLabel(a).localeCompare(channelLabel(b), 'ru')),
    [items, channelLabel],
  )

  const filtered = useMemo(() => {
    let list: SearchQueryRow[] = items
    if (modelF !== 'all')   list = list.filter((i) => i.model_hint === modelF)
    if (channelF !== 'all') list = list.filter((i) => i.purpose === channelF)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter((i) =>
        i.query_text.toLowerCase().includes(q)
        || (i.ww_code ?? '').toLowerCase().includes(q)
        || (i.nomenklatura_wb ?? '').toLowerCase().includes(q)
        || (i.campaign_name ?? '').toLowerCase().includes(q)
        || (i.model_hint ?? '').toLowerCase().includes(q),
      )
    }
    return list
  }, [items, modelF, channelF, search])

  const grouped = useMemo(() => {
    const sortByOrders = (rows: SearchQueryRow[]) =>
      rows.sort((a, b) => (statsMap.get(b.unified_id)?.orders ?? 0) - (statsMap.get(a.unified_id)?.orders ?? 0))

    if (groupBy === 'none') {
      return [{ key: '_all', icon: '', label: '', items: sortByOrders([...filtered]) }]
    }

    const map = new Map<string, SearchQueryRow[]>()
    for (const r of filtered) {
      const k = getGroupKey(r, groupBy)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(r)
    }
    for (const arr of map.values()) sortByOrders(arr)

    const labelMap = groupBy === 'direction' ? GROUP_LABELS_DIRECTION : GROUP_LABELS_ENTITY
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b, 'ru'))
      .map(([key, items]) => {
        const meta = labelMap[key] ?? { icon: '', label: key }
        return { key, icon: meta.icon, label: meta.label, items }
      })
  }, [filtered, statsMap, groupBy])

  const totals = useMemo(() => filtered.reduce(
    (acc, it) => {
      const s = statsMap.get(it.unified_id) ?? ZERO_STATS
      return { f: acc.f + s.frequency, t: acc.t + s.transitions, a: acc.a + s.additions, o: acc.o + s.orders }
    },
    { f: 0, t: 0, a: 0, o: 0 },
  ), [filtered, statsMap])

  return (
    <QueryStatusBoundary isLoading={lq || ls} error={eq ?? es}>
      <div className="flex flex-col h-full">
        <UpdateBar job="search-queries" />

        <div className="px-6 pt-3 pb-2 flex flex-col gap-2 border-b border-border bg-card">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-muted-foreground mr-0.5">Модель:</span>
            {(['all', ...uniqueModels] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setQ('model', m === 'all' ? null : m)}
                className={`px-2.5 py-1 rounded-full text-[12px] font-medium transition-colors ${modelF === m ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
              >
                {m === 'all' ? 'Все' : m}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-muted-foreground mr-0.5">Канал:</span>
            {(['all', ...uniqueChannels] as const).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setQ('channel', c === 'all' ? null : c)}
                className={`px-2.5 py-1 rounded-full text-[12px] font-medium transition-colors ${channelF === c ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
              >
                {c === 'all' ? 'Все' : channelLabel(c)}
              </button>
            ))}
          </div>
        </div>

        <div className="px-6 py-2 border-b border-border flex items-center gap-3 bg-card flex-wrap">
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" aria-hidden />
            <input
              value={search}
              onChange={(e) => setQ('q', e.target.value || null)}
              placeholder="Запрос, артикул, WW-код, кампания…"
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-border rounded-md bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Поиск запросов"
            />
          </div>
          <DateRange from={dateFrom} to={dateTo} min={FIRST} max={LAST}
            onChange={(f, t) => setParams((p) => { p.set('from', f); p.set('to', t); return p })} />
          <GroupBySelector value={groupBy} options={SQ_GROUP_BY_OPTIONS} onChange={setGroupBy} />
          <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">{filtered.length} записей</span>
        </div>

        <div className="flex-1 overflow-auto">
          <div className="overflow-x-auto">
            <table className="min-w-[1100px] table-fixed tabular-nums w-full">
              <colgroup>
                <col className="w-[140px]" />
                <col className="w-[140px]" />
                <col className="w-[100px]" />
                <col className="w-[120px]" />
                <col className="w-[80px]"  />
                <col className="w-[80px]"  />
                <col className="w-[70px]"  />
                <col className="w-[80px]"  />
                <col className="w-[70px]"  />
                <col className="w-[80px]"  />
                <col className="w-[60px]"  />
              </colgroup>
              <thead className="sticky top-0 bg-muted/95 backdrop-blur-sm border-b border-border z-20">
                <tr>
                  <th className={TH}>Запрос</th>
                  <th className={TH}>Артикул</th>
                  <th className={TH}>Канал</th>
                  <th className={TH}>Кампания</th>
                  <th className={THR}>Частота</th>
                  <th className={THR}>Перех.</th>
                  <th className={THR}>CR→корз</th>
                  <th className={THR}>Корз.</th>
                  <th className={THR}>CR→зак</th>
                  <th className={THR}>Заказы</th>
                  <th className={THR}>CRV</th>
                </tr>
              </thead>
              <tbody>
                {grouped.map((g) => {
                  const isCol = !!collapsed[g.key]
                  return (
                    <SectionGroup
                      key={g.key}
                      icon={g.icon}
                      label={g.label}
                      rows={g.items}
                      collapsed={isCol}
                      onToggle={() => toggle(g.key)}
                      statsMap={statsMap}
                      channelLabel={channelLabel}
                      onOpen={(unifiedId) => setQ('open', unifiedId)}
                      hideHeader={groupBy === 'none'}
                    />
                  )
                })}
              </tbody>
              <tfoot className="sticky bottom-0 bg-muted/95 backdrop-blur-sm border-t-2 border-border z-10">
                <tr>
                  <td className="px-2 py-2 text-xs font-medium text-foreground" colSpan={4}>Итого · {filtered.length} запросов</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground">{fmt(totals.f)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground">{fmt(totals.t)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-foreground/80">{pct(totals.a, totals.t)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground">{fmt(totals.a)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-foreground/80">{pct(totals.o, totals.a)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmt(totals.o)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-bold text-foreground">{pct(totals.o, totals.t)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </QueryStatusBoundary>
  )
}

interface SectionGroupProps {
  icon: string
  label: string
  rows: SearchQueryRow[]
  collapsed: boolean
  onToggle: () => void
  statsMap: Map<string, SearchQueryStatsAgg>
  channelLabel: (slug: string | null | undefined) => string
  onOpen: (unifiedId: string) => void
  hideHeader?: boolean
}

function SectionGroup({ icon, label, rows, collapsed, onToggle, statsMap, channelLabel, onOpen, hideHeader }: SectionGroupProps) {
  const showRows = hideHeader || !collapsed
  return (
    <>
      {!hideHeader && (
        <SectionHeader icon={icon} label={label} count={rows.length} collapsed={collapsed} onToggle={onToggle} colSpan={11} />
      )}
      {showRows && rows.length === 0 && (
        <tr>
          <td colSpan={11} className="px-3 py-6 text-center text-[11px] text-muted-foreground">Нет данных</td>
        </tr>
      )}
      {showRows && rows.map((it) => {
        const s = statsMap.get(it.unified_id) ?? ZERO_STATS
        return (
          <tr key={it.unified_id}
              tabIndex={0}
              onClick={() => onOpen(it.unified_id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(it.unified_id) } }}
              className="cursor-pointer transition-colors border-b border-border/50 hover:bg-muted/50 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-inset">
            <td className="px-2 py-2"><span className="font-mono text-xs text-foreground">{it.query_text}</span></td>
            <td className="px-2 py-2 text-xs text-muted-foreground truncate">{it.ww_code ?? it.nomenklatura_wb ?? ''}</td>
            <td className="px-2 py-2">
              {it.purpose
                ? <Badge color="gray" label={channelLabel(it.purpose)} compact />
                : <span className="text-stone-400 text-xs">—</span>}
            </td>
            <td className="px-2 py-2 text-xs text-muted-foreground truncate">{it.campaign_name ?? ''}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm text-foreground/80">{s.frequency > 0 ? fmt(s.frequency) : ''}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm text-foreground/80">{s.transitions > 0 ? fmt(s.transitions) : ''}</td>
            <td className="px-2 py-2 text-right tabular-nums text-[11px] text-muted-foreground">{pct(s.additions, s.transitions)}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm text-foreground/80">{s.additions > 0 ? fmt(s.additions) : ''}</td>
            <td className="px-2 py-2 text-right tabular-nums text-[11px] text-muted-foreground">{pct(s.orders, s.additions)}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm text-foreground font-medium">{s.orders > 0 ? fmt(s.orders) : ''}</td>
            <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-foreground/80">{pct(s.orders, s.transitions)}</td>
          </tr>
        )
      })}
    </>
  )
}
