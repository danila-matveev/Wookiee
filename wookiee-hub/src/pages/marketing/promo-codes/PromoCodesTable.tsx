import { Badge } from "@/components/crm/ui/Badge"
import { derivePromoStatus } from "@/lib/marketing-helpers"
import type { PromoCodeRow } from "@/types/marketing"

export interface PromoCodesTableRow extends PromoCodeRow {
  qty:   number
  sales: number
}

interface PromoCodesTableProps {
  rows: PromoCodesTableRow[]
  footerQty: number
  footerSales: number
  selectedId: number | null
  onRowClick: (id: number) => void
}

const TH  = "px-2 py-2 text-left  text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const THR = "px-2 py-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const fmt  = (n: number) => n.toLocaleString("ru-RU")
const fmtR = (n: number) => `${n.toLocaleString("ru-RU")} ₽`

export function PromoCodesTable({ rows, footerQty, footerSales, selectedId, onRowClick }: PromoCodesTableProps) {
  const footerAvg = footerQty > 0 ? Math.round(footerSales / footerQty) : 0

  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full table-fixed">
        <colgroup>
          <col className="w-[220px]" />
          <col className="w-[120px]" />
          <col className="w-[80px]"  />
          <col className="w-[110px]" />
          <col />
          <col />
          <col />
        </colgroup>
        <thead className="sticky top-0 bg-muted/95 backdrop-blur-sm border-b border-border z-10">
          <tr>
            {["Код", "Канал", "Скидка", "Статус"].map((h) => (
              <th key={h} className={TH}>{h}</th>
            ))}
            {["Продажи, шт", "Продажи, ₽", "Ср. чек, ₽"].map((h) => (
              <th key={h} className={THR}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {rows.map((p) => {
            const s = derivePromoStatus({ status: p.status, qty: p.qty, channel: p.channel })
            const avg = p.qty > 0 ? Math.round(p.sales / p.qty) : 0
            const isUnidentified = s.kind === "unidentified"
            const selected = p.id === selectedId
            return (
              <tr
                key={p.id}
                tabIndex={0}
                onClick={() => onRowClick(p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    onRowClick(p.id)
                  }
                }}
                className={`cursor-pointer transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-inset ${
                  selected ? "bg-muted/60" : "hover:bg-muted/50"
                }`}
              >
                <td className="px-2 py-2.5">
                  <span className={`font-mono text-xs ${isUnidentified ? "text-warning" : "text-foreground"}`}>
                    {p.code.length > 24 ? p.code.slice(0, 24) + "…" : p.code}
                  </span>
                </td>
                <td className="px-2 py-2.5">
                  <Badge tone="secondary">{p.channel ?? "—"}</Badge>
                </td>
                <td className="px-2 py-2.5 text-sm tabular-nums text-foreground/80">
                  {p.discount_pct != null ? `${p.discount_pct}%` : "—"}
                </td>
                <td className="px-2 py-2.5">
                  <Badge tone={s.tone}>{s.label}</Badge>
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-sm font-medium text-foreground">
                  {p.qty > 0 ? fmt(p.qty) : <span className="text-muted-foreground/50">—</span>}
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-sm text-foreground/80">
                  {p.sales > 0 ? fmtR(p.sales) : <span className="text-muted-foreground/50">—</span>}
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-sm text-muted-foreground">
                  {avg > 0 ? fmtR(avg) : <span className="text-muted-foreground/50">—</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot className="sticky bottom-0 bg-muted/95 backdrop-blur-sm border-t-2 border-border z-10">
          <tr>
            <td className="px-2 py-2 text-xs font-medium text-foreground" colSpan={4}>
              Итого · {rows.length} кодов
            </td>
            <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmt(footerQty)}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmtR(footerSales)}</td>
            <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground/80">
              {footerAvg > 0 ? fmtR(footerAvg) : "—"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
