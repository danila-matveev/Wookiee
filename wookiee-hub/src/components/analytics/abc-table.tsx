import { useMemo, useState } from "react"
import type { AbcArticle } from "@/types/api"
import { StatusPill } from "@/components/shared/status-pill"
import { ProgressBar } from "@/components/shared/progress-bar"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

const categoryColors: Record<string, { bg: string; text: string; css: string }> = {
  A: { bg: "bg-emerald-500/15", text: "text-emerald-400", css: "var(--wk-green, #34d399)" },
  B: { bg: "bg-amber-500/15", text: "text-amber-400", css: "var(--wk-amber, #fbbf24)" },
  C: { bg: "bg-red-500/15", text: "text-red-400", css: "var(--wk-red, #f87171)" },
  New: { bg: "bg-blue-500/15", text: "text-blue-400", css: "var(--wk-blue, #60a5fa)" },
}

interface ModelGroup {
  model: string
  articles: AbcArticle[]
  revenue: number
  orders: number
  margin: number
  marginPct: number
  share: number
  drr: number
  category: "A" | "B" | "C" | "New"
}

function CategoryBadge({ category }: { category: "A" | "B" | "C" | "New" }) {
  const colors = categoryColors[category]
  return (
    <span className={cn("inline-flex items-center justify-center w-6 h-6 rounded-md text-[11px] font-bold", colors.bg, colors.text)}>
      {category}
    </span>
  )
}

interface AbcTableProps {
  items: AbcArticle[]
}

export function AbcTable({ items }: AbcTableProps) {
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set())

  const groups = useMemo<ModelGroup[]>(() => {
    const map = new Map<string, AbcArticle[]>()
    for (const item of items) {
      const key = item.model || item.article
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    }

    const totalRevenue = items.reduce((s, i) => s + i.revenue, 0)

    return Array.from(map.entries())
      .map(([model, articles]) => {
        // Sort articles within group by margin desc
        articles.sort((a, b) => b.margin - a.margin)
        const revenue = articles.reduce((s, a) => s + a.revenue, 0)
        const orders = articles.reduce((s, a) => s + a.orders, 0)
        const margin = articles.reduce((s, a) => s + a.margin, 0)
        const marginPct =
          revenue > 0 ? articles.reduce((s, a) => s + a.margin_pct * a.revenue, 0) / revenue : 0
        const advTotal = articles.reduce((s, a) => s + a.adv_total, 0)
        const drr = revenue > 0 ? (advTotal / revenue) * 100 : 0
        const share = totalRevenue > 0 ? (revenue / totalRevenue) * 100 : 0
        // Model category = most common category, or highest revenue article's category
        const category = articles.sort((a, b) => b.revenue - a.revenue)[0].category
        return { model, articles, revenue, orders, margin, marginPct, share, drr, category }
      })
      .sort((a, b) => b.margin - a.margin)
  }, [items])

  const toggleModel = (model: string) => {
    setExpandedModels((prev) => {
      const next = new Set(prev)
      if (next.has(model)) next.delete(model)
      else next.add(model)
      return next
    })
  }

  const thClass =
    "text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-3.5 py-2.5"
  const thRight = cn(thClass, "text-right")

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={thClass}>Модель / Артикул</th>
              <th className={cn(thClass, "w-12 text-center")}>Статус</th>
              <th className={cn(thClass, "w-10 text-center")}>ABC</th>
              <th className={thRight}>Выручка</th>
              <th className={thRight}>Заказы</th>
              <th className={thRight}>Маржа ₽</th>
              <th className={thRight}>Маржа %</th>
              <th className={thRight}>Доля %</th>
              <th className={thRight}>DRR %</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => {
              const isExpanded = expandedModels.has(group.model)
              const hasMultiple = group.articles.length > 1

              return (
                <ModelGroupRows
                  key={group.model}
                  group={group}
                  isExpanded={isExpanded}
                  hasMultiple={hasMultiple}
                  onToggle={() => toggleModel(group.model)}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ModelGroupRows({
  group,
  isExpanded,
  hasMultiple,
  onToggle,
}: {
  group: ModelGroup
  isExpanded: boolean
  hasMultiple: boolean
  onToggle: () => void
}) {
  return (
    <>
      {/* Model summary row */}
      <tr
        className={cn(
          "border-b border-border/[0.22] hover:bg-bg-hover transition-colors",
          hasMultiple && "cursor-pointer",
          isExpanded && "bg-bg-soft",
        )}
        onClick={hasMultiple ? onToggle : undefined}
      >
        <td className="px-3.5 py-2.5 text-[13px] font-medium">
          <div className="flex items-center gap-2">
            {hasMultiple && (
              <span className={cn("text-[10px] text-muted-foreground transition-transform", isExpanded && "rotate-90")}>
                ▶
              </span>
            )}
            <span>{group.model}</span>
            {hasMultiple && (
              <span className="text-[11px] text-muted-foreground">
                ({group.articles.length})
              </span>
            )}
          </div>
        </td>
        <td className="px-3.5 py-2.5 text-center">
          {/* Model row: no status */}
        </td>
        <td className="px-3.5 py-2.5 text-center">
          <CategoryBadge category={group.category} />
        </td>
        <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
          {formatCurrency(group.revenue)}
        </td>
        <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
          {formatNumber(group.orders)}
        </td>
        <td className="px-3.5 py-2.5 text-right text-[13px] font-mono">
          {formatCurrency(group.margin)}
        </td>
        <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", group.marginPct > 20 ? "text-wk-green" : "")}>
          {formatPercent(group.marginPct)}
        </td>
        <td className="px-3.5 py-2.5 text-right">
          <div className="flex items-center justify-end gap-2">
            <ProgressBar value={group.share} className="w-16 h-1" />
            <span className="text-[13px] font-mono w-12 text-right">
              {formatPercent(group.share)}
            </span>
          </div>
        </td>
        <td className={cn("px-3.5 py-2.5 text-right text-[13px] font-mono", group.drr > 15 ? "text-red-400" : "")}>
          {formatPercent(group.drr)}
        </td>
      </tr>

      {/* Expanded article rows */}
      {isExpanded &&
        group.articles.map((article) => (
          <tr
            key={article.article}
            className="border-b border-border/[0.12] bg-bg-soft/50 hover:bg-bg-hover transition-colors"
          >
            <td className="px-3.5 py-2 text-[12px] text-muted-foreground pl-10">
              {article.article}
              {article.color_code && (
                <span className="ml-2 text-[11px] text-text-dim">
                  {article.color_code}
                </span>
              )}
            </td>
            <td className="px-3.5 py-2 text-center">
              {article.status && (
                <StatusPill
                  label={article.status}
                  color="var(--text-dim)"
                />
              )}
            </td>
            <td className="px-3.5 py-2 text-center">
              <CategoryBadge category={article.category} />
            </td>
            <td className="px-3.5 py-2 text-right text-[12px] font-mono text-muted-foreground">
              {formatCurrency(article.revenue)}
            </td>
            <td className="px-3.5 py-2 text-right text-[12px] font-mono text-muted-foreground">
              {formatNumber(article.orders)}
            </td>
            <td className="px-3.5 py-2 text-right text-[12px] font-mono text-muted-foreground">
              {formatCurrency(article.margin)}
            </td>
            <td className={cn("px-3.5 py-2 text-right text-[12px] font-mono", article.margin_pct > 20 ? "text-wk-green" : "text-muted-foreground")}>
              {formatPercent(article.margin_pct)}
            </td>
            <td className="px-3.5 py-2 text-right text-[12px] font-mono text-muted-foreground">
              {formatPercent(article.share)}
            </td>
            <td className={cn("px-3.5 py-2 text-right text-[12px] font-mono", article.drr > 15 ? "text-red-400" : "text-muted-foreground")}>
              {formatPercent(article.drr)}
            </td>
          </tr>
        ))}
    </>
  )
}
