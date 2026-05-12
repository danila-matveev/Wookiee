import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import { QueryStatusBoundary } from "@/components/crm/ui/QueryStatusBoundary"
import { Button } from "@/components/crm/ui/Button"
import { KpiCard } from "@/components/marketing/KpiCard"
import { UpdateBar } from "@/components/marketing/UpdateBar"
import { DateRange } from "@/components/marketing/DateRange"
import { usePromoCodes, usePromoStatsWeekly } from "@/hooks/marketing/use-promo-codes"
import { useLastSync } from "@/hooks/marketing/use-sync-log"
import { formatDateTime } from "@/lib/format"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"
import { PromoPanel, type PromoPanelMode } from "./promo-codes/PromoPanel"

const FIRST = "2025-07-28"
const LAST  = new Date().toISOString().slice(0, 10)
const DEFAULT_FROM = "2026-03-30"

const fmt  = (n: number) => n.toLocaleString("ru-RU")
const fmtR = (n: number) => `${n.toLocaleString("ru-RU")} ₽`

export function PromoCodesPage() {
  const [params, setParams] = useSearchParams()
  const search   = params.get("q")    ?? ""
  const dateFrom = params.get("from") ?? DEFAULT_FROM
  const dateTo   = params.get("to")   ?? LAST

  const adding   = params.get("add") === "1"
  const openParam = params.get("open")
  const openId   = openParam ? Number(openParam) : null
  const editParam = params.get("edit") === "1"

  const { data: promos = [], isLoading: lp, error: ep } = usePromoCodes()
  const { data: weekly = [], isLoading: lw, error: ew } = usePromoStatsWeekly()
  const { data: lastSync } = useLastSync("promo_codes_sync")

  // Aggregate weekly stats per promo within the date range.
  const enriched = useMemo(() => {
    const inRange = weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo)
    const byId = new Map<number, { qty: number; sales: number }>()
    for (const w of inRange) {
      const cur = byId.get(w.promo_code_id) ?? { qty: 0, sales: 0 }
      cur.qty   += w.orders_count
      cur.sales += w.sales_rub
      byId.set(w.promo_code_id, cur)
    }
    return promos.map((p) => ({
      ...p,
      qty:   byId.get(p.id)?.qty   ?? 0,
      sales: byId.get(p.id)?.sales ?? 0,
    }))
  }, [promos, weekly, dateFrom, dateTo])

  const filtered = useMemo(() => {
    let l = enriched
    if (search) {
      const q = search.toLowerCase()
      l = l.filter((p) =>
        p.code.toLowerCase().includes(q) || p.channel?.toLowerCase().includes(q),
      )
    }
    return [...l].sort((a, b) => b.sales - a.sales)
  }, [enriched, search])

  // KPI: per spec, ВСЕ промокоды (not filtered).
  const totalPromosQty   = useMemo(() => enriched.reduce((s, p) => s + p.qty, 0),   [enriched])
  const totalPromosSales = useMemo(() => enriched.reduce((s, p) => s + p.sales, 0), [enriched])
  const totalPromosAvg   = totalPromosQty > 0 ? Math.round(totalPromosSales / totalPromosQty) : 0
  const activeCount      = promos.filter((p) => p.status === "active").length

  // Footer totals — по filtered (sum того, что юзер видит).
  const footerQty   = useMemo(() => filtered.reduce((s, p) => s + p.qty, 0),   [filtered])
  const footerSales = useMemo(() => filtered.reduce((s, p) => s + p.sales, 0), [filtered])

  const setParam = (k: string, v: string | null) =>
    setParams((p) => { v == null ? p.delete(k) : p.set(k, v); return p })

  const openAdd = () => {
    setParams((p) => {
      p.set("add", "1")
      p.delete("open")
      p.delete("edit")
      return p
    })
  }
  const openView = (id: number) => {
    setParams((p) => {
      p.set("open", String(id))
      p.delete("add")
      p.delete("edit")
      return p
    })
  }
  const closePanel = () => {
    setParams((p) => {
      p.delete("add")
      p.delete("open")
      p.delete("edit")
      return p
    })
  }

  // Resolve panel mode + target id.
  const panelMode: PromoPanelMode | null = adding
    ? "add"
    : openId != null && Number.isFinite(openId) && openId > 0
      ? (editParam ? "edit" : "view")
      : null
  const panelOpen = panelMode != null

  const handleModeChange = (next: PromoPanelMode) => {
    if (next === "edit") setParam("edit", "1")
    else if (next === "view") setParam("edit", null)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 pt-5 pb-4 border-b border-border bg-card">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h1
              className="text-foreground"
              style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: "italic" }}
            >
              Промокоды
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">Статистика по кодам скидок</p>
          </div>
          <Button variant="primary" onClick={openAdd} className="gap-1">
            <Plus className="w-3.5 h-3.5" aria-hidden />
            Добавить
          </Button>
        </div>
        <div className="grid grid-cols-4 gap-3 mt-4">
          <KpiCard label="Активных"     value={String(activeCount)}                                                sub={`из ${promos.length}`} />
          <KpiCard label="Продажи, шт"  value={fmt(totalPromosQty)} />
          <KpiCard label="Продажи, ₽"   value={fmtR(totalPromosSales)} />
          <KpiCard label="Ср. чек, ₽"   value={totalPromosAvg > 0 ? fmtR(totalPromosAvg) : "—"} />
        </div>
      </div>

      <UpdateBar
        lastUpdate={lastSync?.finished_at ? formatDateTime(lastSync.finished_at) : undefined}
        weeksCovered={lastSync?.weeks_covered ?? undefined}
        status={lastSync?.status === "failed" ? "failed" : lastSync?.status === "success" ? "success" : "unknown"}
      />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <div className="px-6 py-2 border-b border-border flex items-center gap-3 bg-card flex-wrap">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" aria-hidden />
              <input
                value={search}
                onChange={(e) => setParam("q", e.target.value || null)}
                placeholder="Код или канал…"
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-border rounded-md bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label="Поиск промокода"
              />
            </div>
            <DateRange
              from={dateFrom}
              to={dateTo}
              min={FIRST}
              max={LAST}
              onChange={(f, t) => setParams((p) => { p.set("from", f); p.set("to", t); return p })}
            />
            <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">
              {filtered.length} кодов
            </span>
          </div>

          <QueryStatusBoundary isLoading={lp || lw} error={ep ?? ew}>
            <PromoCodesTable
              rows={filtered}
              footerQty={footerQty}
              footerSales={footerSales}
              selectedId={openId}
              onRowClick={openView}
            />
          </QueryStatusBoundary>
        </div>

        {panelOpen && panelMode != null && (
          <PromoPanel
            mode={panelMode}
            promoId={panelMode === "add" ? null : openId}
            onClose={closePanel}
            onModeChange={handleModeChange}
          />
        )}
      </div>
    </div>
  )
}
