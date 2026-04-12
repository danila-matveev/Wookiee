import { useMemo } from "react"
import { X } from "lucide-react"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { cn } from "@/lib/utils"
import { formatCurrency, formatPercent } from "@/lib/format"
import type { ModelRow } from "@/types/api"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelDetailDrawerProps {
  open: boolean
  onClose: () => void
  mpKey: string
  modelName: string
  rows: ModelRow[]
}

interface ExpenseSlice {
  name: string
  value: number
  color: string
}

// ---------------------------------------------------------------------------
// Colors for pie
// ---------------------------------------------------------------------------

const PIE_COLORS = [
  "var(--accent)",
  "var(--wk-blue)",
  "var(--wk-green)",
  "var(--wk-yellow)",
  "var(--wk-red)",
  "var(--wk-pink)",
  "#8884d8",
  "#82ca9d",
  "#ffc658",
  "#ff7c7c",
  "#a4de6c",
]

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ModelDetailDrawer({
  open,
  onClose,
  mpKey,
  modelName,
  rows,
}: ModelDetailDrawerProps) {
  const currentRows = useMemo(
    () =>
      rows.filter(
        (r) =>
          r.period === "current" &&
          r.mp === mpKey &&
          r.model === modelName,
      ),
    [rows, mpKey, modelName],
  )

  const previousRows = useMemo(
    () =>
      rows.filter(
        (r) =>
          r.period === "previous" &&
          r.mp === mpKey &&
          r.model === modelName,
      ),
    [rows, mpKey, modelName],
  )

  const cur = useMemo(() => {
    if (!currentRows.length) return null
    return {
      revenue_before_spp: currentRows.reduce((s, r) => s + r.revenue_before_spp, 0),
      margin: currentRows.reduce((s, r) => s + r.margin, 0),
      margin_pct: currentRows.reduce((s, r) => s + r.margin_pct, 0) / currentRows.length,
      sales_count: currentRows.reduce((s, r) => s + r.sales_count, 0),
      adv_internal: currentRows.reduce((s, r) => s + r.adv_internal, 0),
      adv_external: currentRows.reduce((s, r) => s + r.adv_external, 0),
      cost_of_goods: currentRows.reduce((s, r) => s + r.cost_of_goods, 0),
      drr_pct: currentRows.reduce((s, r) => s + r.drr_pct, 0) / currentRows.length,
    }
  }, [currentRows])

  const prev = useMemo(() => {
    if (!previousRows.length) return null
    return {
      revenue_before_spp: previousRows.reduce((s, r) => s + r.revenue_before_spp, 0),
      margin: previousRows.reduce((s, r) => s + r.margin, 0),
      sales_count: previousRows.reduce((s, r) => s + r.sales_count, 0),
    }
  }, [previousRows])

  const expenses: ExpenseSlice[] = useMemo(() => {
    if (!cur) return []
    const items = [
      { name: "Себестоимость", value: cur.cost_of_goods },
      { name: "Реклама внутр.", value: cur.adv_internal },
      { name: "Реклама внешн.", value: cur.adv_external },
    ].filter((e) => e.value > 0)

    return items.map((e, i) => ({
      ...e,
      color: PIE_COLORS[i % PIE_COLORS.length],
    }))
  }, [cur])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/10 backdrop-blur-[2px] transition-opacity duration-200"
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 z-50 h-full w-full max-w-md bg-background border-l border-border shadow-xl overflow-y-auto transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="sticky top-0 bg-background z-10 flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 className="text-base font-semibold">{modelName}</h2>
            <p className="text-[12px] text-muted-foreground">{mpKey === "wb" ? "Wildberries" : mpKey === "ozon" ? "Ozon" : mpKey}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-bg-hover transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {!cur ? (
          <div className="p-6 text-center text-muted-foreground">Нет данных</div>
        ) : (
          <div className="p-4 space-y-6">
            {/* Sales metrics */}
            <section>
              <h3 className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-3">
                Продажи
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <MetricItem
                  label="Продажи до СПП"
                  value={formatCurrency(cur.revenue_before_spp)}
                  delta={prev ? pctDelta(cur.revenue_before_spp, prev.revenue_before_spp) : undefined}
                />
                <MetricItem
                  label="Маржа"
                  value={formatCurrency(cur.margin)}
                  delta={prev ? pctDelta(cur.margin, prev.margin) : undefined}
                />
                <MetricItem
                  label="Маржа %"
                  value={formatPercent(cur.margin_pct)}
                />
                <MetricItem
                  label="Продажи шт"
                  value={String(cur.sales_count)}
                  delta={prev ? pctDelta(cur.sales_count, prev.sales_count) : undefined}
                />
                <MetricItem
                  label="ДРР"
                  value={formatPercent(cur.drr_pct)}
                />
                <MetricItem
                  label="Ср.чек"
                  value={cur.sales_count ? formatCurrency(Math.round(cur.revenue_before_spp / cur.sales_count)) : "--"}
                />
              </div>
            </section>

            {/* Expenses pie */}
            {expenses.length > 0 && (
              <section>
                <h3 className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-3">
                  Расходы
                </h3>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={expenses}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                    >
                      {expenses.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(value: number) => [formatCurrency(value), ""]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-3 justify-center mt-2">
                  {expenses.map((e) => (
                    <div key={e.name} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: e.color }} />
                      {e.name}: {formatCurrency(e.value)}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function pctDelta(cur: number, prev: number): number {
  if (!prev) return 0
  return Math.round(((cur - prev) / Math.abs(prev)) * 1000) / 10
}

function MetricItem({
  label,
  value,
  delta,
}: {
  label: string
  value: string
  delta?: number
}) {
  return (
    <div className="bg-bg-soft rounded-lg p-3">
      <div className="text-[11px] text-muted-foreground mb-1">{label}</div>
      <div className="text-[15px] font-semibold tabular-nums">{value}</div>
      {delta !== undefined && delta !== 0 && (
        <span
          className={cn(
            "text-[11px] font-semibold tabular-nums",
            delta > 0 ? "text-wk-green" : "text-wk-red",
          )}
        >
          {delta > 0 ? "\u25B2" : "\u25BC"} {Math.abs(delta)}%
        </span>
      )}
    </div>
  )
}
