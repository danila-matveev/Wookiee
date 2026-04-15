import { useState, useMemo } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { formatCurrency, formatPercent } from "@/lib/format"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceByModel } from "@/lib/api/finance"
import { useFilterParams } from "@/stores/filters"
import type { ModelRow } from "@/types/api"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AggregatedRow {
  key: string
  mp: string
  orders_rub: number
  avg_check: number
  avg_check_delta: number
  revenue_before_spp: number
  revenue_delta: number
  margin: number
  margin_delta: number
  margin_pct: number
  margin_pct_delta: number
  adv_internal: number
  adv_internal_delta: number
  adv_external: number
  adv_external_delta: number
  children?: AggregatedRow[]
}

type SortField = "orders_rub" | "avg_check" | "revenue_before_spp" | "margin" | "margin_pct" | "adv_internal" | "adv_external"
type SortDir = "asc" | "desc"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mpLabel(mp: string): string {
  if (mp === "wb") return "WB"
  if (mp === "ozon") return "Ozon"
  return mp
}

function pctDelta(cur: number, prev: number): number {
  if (!prev) return 0
  return Math.round(((cur - prev) / Math.abs(prev)) * 1000) / 10
}

function aggregate(rows: ModelRow[]): AggregatedRow[] {
  // Group by mp
  const byMp = new Map<string, { current: ModelRow[]; previous: ModelRow[] }>()

  for (const r of rows) {
    if (!byMp.has(r.mp)) byMp.set(r.mp, { current: [], previous: [] })
    byMp.get(r.mp)![r.period].push(r)
  }

  const result: AggregatedRow[] = []

  for (const [mp, periods] of byMp) {
    const cur = periods.current
    const prev = periods.previous

    const cRevenue = cur.reduce((s, r) => s + r.revenue_before_spp, 0)
    const cMargin = cur.reduce((s, r) => s + r.margin, 0)
    const cSales = cur.reduce((s, r) => s + r.sales_count, 0)
    const cAdvInt = cur.reduce((s, r) => s + r.adv_internal, 0)
    const cAdvExt = cur.reduce((s, r) => s + r.adv_external, 0)
    const cAvgCheck = cSales ? cRevenue / cSales : 0

    const pRevenue = prev.reduce((s, r) => s + r.revenue_before_spp, 0)
    const pMargin = prev.reduce((s, r) => s + r.margin, 0)
    const pSales = prev.reduce((s, r) => s + r.sales_count, 0)
    const pAdvInt = prev.reduce((s, r) => s + r.adv_internal, 0)
    const pAdvExt = prev.reduce((s, r) => s + r.adv_external, 0)
    const pAvgCheck = pSales ? pRevenue / pSales : 0

    const cMarginPct = cRevenue ? (cMargin / cRevenue) * 100 : 0
    const pMarginPct = pRevenue ? (pMargin / pRevenue) * 100 : 0

    // Build per-model children
    const models = new Set(rows.filter((r) => r.mp === mp).map((r) => r.model))
    const children: AggregatedRow[] = []

    for (const model of models) {
      const mc = cur.filter((r) => r.model === model)
      const mp2 = prev.filter((r) => r.model === model)

      const mcRev = mc.reduce((s, r) => s + r.revenue_before_spp, 0)
      const mcMar = mc.reduce((s, r) => s + r.margin, 0)
      const mcSales = mc.reduce((s, r) => s + r.sales_count, 0)
      const mcAdvI = mc.reduce((s, r) => s + r.adv_internal, 0)
      const mcAdvE = mc.reduce((s, r) => s + r.adv_external, 0)
      const mcAvg = mcSales ? mcRev / mcSales : 0
      const mcMarPct = mcRev ? (mcMar / mcRev) * 100 : 0

      const mpRev = mp2.reduce((s, r) => s + r.revenue_before_spp, 0)
      const mpMar = mp2.reduce((s, r) => s + r.margin, 0)
      const mpSales2 = mp2.reduce((s, r) => s + r.sales_count, 0)
      const mpAdvI = mp2.reduce((s, r) => s + r.adv_internal, 0)
      const mpAdvE = mp2.reduce((s, r) => s + r.adv_external, 0)
      const mpAvg = mpSales2 ? mpRev / mpSales2 : 0
      const mpMarPct = mpRev ? (mpMar / mpRev) * 100 : 0

      children.push({
        key: `${mp}-${model}`,
        mp: model,
        orders_rub: mcRev,
        avg_check: mcAvg,
        avg_check_delta: pctDelta(mcAvg, mpAvg),
        revenue_before_spp: mcRev,
        revenue_delta: pctDelta(mcRev, mpRev),
        margin: mcMar,
        margin_delta: pctDelta(mcMar, mpMar),
        margin_pct: mcMarPct,
        margin_pct_delta: pctDelta(mcMarPct, mpMarPct),
        adv_internal: mcAdvI,
        adv_internal_delta: pctDelta(mcAdvI, mpAdvI),
        adv_external: mcAdvE,
        adv_external_delta: pctDelta(mcAdvE, mpAdvE),
      })
    }

    result.push({
      key: mp,
      mp: mpLabel(mp),
      orders_rub: cRevenue,
      avg_check: cAvgCheck,
      avg_check_delta: pctDelta(cAvgCheck, pAvgCheck),
      revenue_before_spp: cRevenue,
      revenue_delta: pctDelta(cRevenue, pRevenue),
      margin: cMargin,
      margin_delta: pctDelta(cMargin, pMargin),
      margin_pct: cMarginPct,
      margin_pct_delta: pctDelta(cMarginPct, pMarginPct),
      adv_internal: cAdvInt,
      adv_internal_delta: pctDelta(cAdvInt, pAdvInt),
      adv_external: cAdvExt,
      adv_external_delta: pctDelta(cAdvExt, pAdvExt),
      children,
    })
  }

  // ИТОГО row
  const allCur = rows.filter((r) => r.period === "current")
  const allPrev = rows.filter((r) => r.period === "previous")
  const tRev = allCur.reduce((s, r) => s + r.revenue_before_spp, 0)
  const tMar = allCur.reduce((s, r) => s + r.margin, 0)
  const tSales = allCur.reduce((s, r) => s + r.sales_count, 0)
  const tAdvI = allCur.reduce((s, r) => s + r.adv_internal, 0)
  const tAdvE = allCur.reduce((s, r) => s + r.adv_external, 0)
  const tAvg = tSales ? tRev / tSales : 0
  const tMarPct = tRev ? (tMar / tRev) * 100 : 0

  const pRev = allPrev.reduce((s, r) => s + r.revenue_before_spp, 0)
  const pMar = allPrev.reduce((s, r) => s + r.margin, 0)
  const pSales = allPrev.reduce((s, r) => s + r.sales_count, 0)
  const pAdvI = allPrev.reduce((s, r) => s + r.adv_internal, 0)
  const pAdvE = allPrev.reduce((s, r) => s + r.adv_external, 0)
  const pAvg = pSales ? pRev / pSales : 0
  const pMarPct = pRev ? (pMar / pRev) * 100 : 0

  result.push({
    key: "total",
    mp: "ИТОГО",
    orders_rub: tRev,
    avg_check: tAvg,
    avg_check_delta: pctDelta(tAvg, pAvg),
    revenue_before_spp: tRev,
    revenue_delta: pctDelta(tRev, pRev),
    margin: tMar,
    margin_delta: pctDelta(tMar, pMar),
    margin_pct: tMarPct,
    margin_pct_delta: pctDelta(tMarPct, pMarPct),
    adv_internal: tAdvI,
    adv_internal_delta: pctDelta(tAdvI, pAdvI),
    adv_external: tAdvE,
    adv_external_delta: pctDelta(tAdvE, pAdvE),
  })

  return result
}

// ---------------------------------------------------------------------------
// Delta cell
// ---------------------------------------------------------------------------

function DeltaCell({ value }: { value: number }) {
  if (value === 0) return <span className="text-muted-foreground">--</span>
  return (
    <span className={cn("text-[11px] font-semibold tabular-nums", value > 0 ? "text-wk-red" : "text-wk-green")}>
      {value > 0 ? "\u25B2" : "\u25BC"}{Math.abs(value)}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

const columns: { label: string; field: SortField; format: (v: number) => string }[] = [
  { label: "Заказы до СПП \u20BD", field: "orders_rub", format: (v) => formatCurrency(v) },
  { label: "Ср.чек", field: "avg_check", format: (v) => formatCurrency(Math.round(v)) },
  { label: "Продажи до СПП \u20BD", field: "revenue_before_spp", format: (v) => formatCurrency(v) },
  { label: "Маржа \u20BD", field: "margin", format: (v) => formatCurrency(v) },
  { label: "Маржа %", field: "margin_pct", format: (v) => formatPercent(v) },
  { label: "Реклама внутр.", field: "adv_internal", format: (v) => formatCurrency(v) },
  { label: "Реклама внешн.", field: "adv_external", format: (v) => formatCurrency(v) },
]

const deltaField: Record<SortField, keyof AggregatedRow> = {
  orders_rub: "revenue_delta",
  avg_check: "avg_check_delta",
  revenue_before_spp: "revenue_delta",
  margin: "margin_delta",
  margin_pct: "margin_pct_delta",
  adv_internal: "adv_internal_delta",
  adv_external: "adv_external_delta",
}

interface ModelTableProps {
  className?: string
  onRowClick?: (mpKey: string, model: string) => void
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}

export function ModelTable({ className, onRowClick }: ModelTableProps) {
  const params = useFilterParams()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [sort, setSort] = useState<{ field: SortField; dir: SortDir }>({ field: "orders_rub", dir: "desc" })

  const { data, loading, error } = useApiQuery(
    () => fetchFinanceByModel({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  const rows = useMemo(() => {
    if (!data) return []
    return aggregate(data)
  }, [data])

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSort = (field: SortField) => {
    setSort((prev) => ({
      field,
      dir: prev.field === field && prev.dir === "desc" ? "asc" : "desc",
    }))
  }

  // Sort rows (keep ИТОГО at bottom)
  const sortedRows = useMemo(() => {
    const totalRow = rows.find((r) => r.key === "total")
    const other = rows.filter((r) => r.key !== "total")
    const sorted = [...other].sort((a, b) => {
      const av = a[sort.field] as number
      const bv = b[sort.field] as number
      return sort.dir === "desc" ? bv - av : av - bv
    })
    if (totalRow) sorted.push(totalRow)
    return sorted
  }, [rows, sort])

  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4 overflow-x-auto", className)}>
      <h3 className="text-sm font-semibold mb-3">По маркетплейсам</h3>
      {loading ? (
        <TableSkeleton />
      ) : error || !data ? (
        <div className="text-muted-foreground text-sm text-center py-4">{error ?? "Нет данных"}</div>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border/50">
              <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold py-2 pr-4 w-40">
                МП
              </th>
              {columns.map((col) => (
                <th
                  key={col.field}
                  className="text-right text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold py-2 px-2 cursor-pointer hover:text-foreground transition-colors select-none whitespace-nowrap"
                  onClick={() => handleSort(col.field)}
                >
                  {col.label}
                  {sort.field === col.field && (
                    <span className="ml-0.5">{sort.dir === "desc" ? "\u2193" : "\u2191"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => {
              const isTotal = row.key === "total"
              const hasChildren = !!row.children?.length
              const isExpanded = expanded.has(row.key)

              return (
                <RowGroup
                  key={row.key}
                  row={row}
                  isTotal={isTotal}
                  hasChildren={hasChildren}
                  isExpanded={isExpanded}
                  onToggle={() => toggleExpand(row.key)}
                  onRowClick={onRowClick}
                />
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row group (parent + children)
// ---------------------------------------------------------------------------

function RowGroup({
  row,
  isTotal,
  hasChildren,
  isExpanded,
  onToggle,
  onRowClick,
}: {
  row: AggregatedRow
  isTotal: boolean
  hasChildren: boolean
  isExpanded: boolean
  onToggle: () => void
  onRowClick?: (mpKey: string, model: string) => void
}) {
  return (
    <>
      <tr
        className={cn(
          "border-b border-border/20 hover:bg-bg-hover/50 transition-colors duration-100",
          isTotal && "font-semibold border-t border-border/50",
          hasChildren && "cursor-pointer",
        )}
        onClick={() => hasChildren && onToggle()}
      >
        <td className="py-2 pr-4">
          <div className="flex items-center gap-1">
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="size-3.5 text-muted-foreground" />
              ) : (
                <ChevronRight className="size-3.5 text-muted-foreground" />
              )
            ) : (
              <span className="w-3.5" />
            )}
            <span>{row.mp}</span>
          </div>
        </td>
        {columns.map((col) => (
          <td key={col.field} className="text-right py-2 px-2 tabular-nums whitespace-nowrap">
            <div>{col.format(row[col.field] as number)}</div>
            <DeltaCell value={row[deltaField[col.field]] as number} />
          </td>
        ))}
      </tr>
      {isExpanded &&
        row.children?.map((child) => (
          <tr
            key={child.key}
            className="border-b border-border/10 hover:bg-bg-hover/30 transition-colors duration-100 cursor-pointer"
            onClick={() => onRowClick?.(row.key, child.mp)}
          >
            <td className="py-1.5 pr-4 pl-6 text-muted-foreground text-[12px]">{child.mp}</td>
            {columns.map((col) => (
              <td key={col.field} className="text-right py-1.5 px-2 tabular-nums text-[12px] whitespace-nowrap">
                <div>{col.format(child[col.field] as number)}</div>
                <DeltaCell value={child[deltaField[col.field]] as number} />
              </td>
            ))}
          </tr>
        ))}
    </>
  )
}
