import { useState, useMemo } from "react"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface UnitRow {
  model: string
  sales_count: number
  revenue_per_unit: number
  cogs_per_unit: number
  ad_per_unit: number
  margin_per_unit: number
  margin_pct: number
  drr_pct: number
  turnover_days: number | null
  avg_stock: number | null
}

type SortKey = keyof Omit<UnitRow, "model">

interface UnitTableProps {
  rows: UnitRow[]
}

function marginColor(pct: number): string {
  if (pct < 15) return "text-red-400"
  if (pct <= 25) return "text-amber-400"
  return "text-emerald-400"
}

function turnoverColor(days: number | null): string {
  if (days == null) return "text-muted-foreground"
  if (days > 60) return "text-red-400"
  if (days >= 30) return "text-amber-400"
  return "text-emerald-400"
}

const columns: { key: SortKey; label: string }[] = [
  { key: "sales_count", label: "Продажи" },
  { key: "revenue_per_unit", label: "Выручка/ед" },
  { key: "cogs_per_unit", label: "Себест./ед" },
  { key: "ad_per_unit", label: "Реклама/ед" },
  { key: "margin_per_unit", label: "Маржа/ед" },
  { key: "margin_pct", label: "Маржа %" },
  { key: "drr_pct", label: "DRR %" },
  { key: "turnover_days", label: "Оборач. дн." },
  { key: "avg_stock", label: "Ср. остаток" },
]

export function UnitTable({ rows }: UnitTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("margin_per_unit")
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity
      const bv = b[sortKey] ?? -Infinity
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
  }, [rows, sortKey, sortAsc])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  const thBase =
    "text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-3.5 py-2.5 cursor-pointer select-none hover:text-foreground transition-colors"
  const thRight = cn(thBase, "text-right")

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={cn(thBase, "text-left")}>Модель</th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={thRight}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1 text-[9px]">
                      {sortAsc ? "\u25B2" : "\u25BC"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length + 1}
                  className="text-center py-12 text-muted-foreground text-sm"
                >
                  Нет данных
                </td>
              </tr>
            )}
            {sorted.map((row) => (
              <tr
                key={row.model}
                className="border-b border-border/[0.22] hover:bg-bg-hover transition-colors"
              >
                <td className="px-3.5 py-2.5 text-[13px] font-medium whitespace-nowrap">
                  {row.model}
                </td>
                <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
                  {formatNumber(row.sales_count)}
                </td>
                <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
                  {formatCurrency(Math.round(row.revenue_per_unit))}
                </td>
                <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
                  {formatCurrency(Math.round(row.cogs_per_unit))}
                </td>
                <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
                  {formatCurrency(Math.round(row.ad_per_unit))}
                </td>
                <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", marginColor(row.margin_pct))}>
                  {formatCurrency(Math.round(row.margin_per_unit))}
                </td>
                <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", marginColor(row.margin_pct))}>
                  {formatPercent(row.margin_pct)}
                </td>
                <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", row.drr_pct > 15 ? "text-red-400" : "")}>
                  {formatPercent(row.drr_pct)}
                </td>
                <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", turnoverColor(row.turnover_days))}>
                  {row.turnover_days != null ? formatNumber(row.turnover_days) : "\u2014"}
                </td>
                <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
                  {row.avg_stock != null ? formatNumber(row.avg_stock) : "\u2014"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
