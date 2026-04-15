// ---------------------------------------------------------------------------
// Supply Product Table — main planning table with frozen columns
// ---------------------------------------------------------------------------

import { useState, useMemo, useCallback, useRef, useEffect, memo } from "react"
import { useSupplyStore } from "@/stores/supply"
import { calcSupplyChain, calcSuggestedQty, getAlertLevel } from "@/lib/supply-calc"
import type { SupplyProduct, SupplyBlockResult, AlertLevel } from "@/types/supply"

// ── Alert helpers ───────────────────────────────────────────────────────────

function alertBg(level: AlertLevel): string {
  switch (level) {
    case "critical": return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
    case "warning": return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
    default: return ""
  }
}

function alertDot(level: AlertLevel): string {
  switch (level) {
    case "critical": return "bg-red-500"
    case "warning": return "bg-amber-500"
    default: return "bg-emerald-500"
  }
}

// ── Status helpers ──────────────────────────────────────────────────────────

function statusColor(status: string): string {
  switch (status) {
    case "delivered": return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30"
    case "shipped": return "bg-blue-100 text-blue-800 dark:bg-blue-900/30"
    case "ordered": return "bg-violet-100 text-violet-800 dark:bg-violet-900/30"
    default: return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800"
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "delivered": return "Прибыло"
    case "shipped": return "В пути"
    case "ordered": return "Заказано"
    case "draft": return "Черновик"
    default: return status
  }
}

// ── EditableCell ────────────────────────────────────────────────────────────

interface EditableCellProps {
  value: number
  placeholder: number
  orderId: string
  barcode: string
  disabled?: boolean
  onSave: (orderId: string, barcode: string, quantity: number) => void
}

const EditableCell = memo(function EditableCell({
  value,
  placeholder,
  orderId,
  barcode,
  disabled,
  onSave,
}: EditableCellProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string>(String(value || ""))
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  // Sync external value changes
  useEffect(() => {
    if (!editing) {
      setDraft(String(value || ""))
    }
  }, [value, editing])

  const handleCommit = useCallback(() => {
    setEditing(false)
    const parsed = parseInt(draft, 10)
    const qty = isNaN(parsed) || parsed < 0 ? 0 : parsed
    if (qty !== value) {
      onSave(orderId, barcode, qty)
    }
  }, [draft, value, orderId, barcode, onSave])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleCommit()
      } else if (e.key === "Escape") {
        setDraft(String(value || ""))
        setEditing(false)
      }
    },
    [handleCommit, value],
  )

  if (disabled) {
    return (
      <span className="tabular-nums text-muted-foreground">
        {value || "—"}
      </span>
    )
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="number"
        min={0}
        className="w-full h-7 px-1 text-sm tabular-nums text-center bg-background border border-primary/40 rounded outline-none focus:ring-1 focus:ring-primary/50"
        value={draft}
        placeholder={placeholder ? String(placeholder) : "0"}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleCommit}
        onKeyDown={handleKeyDown}
      />
    )
  }

  return (
    <button
      type="button"
      className="w-full h-7 px-1 text-sm tabular-nums text-center rounded hover:bg-muted/60 transition-colors cursor-text"
      onClick={() => setEditing(true)}
    >
      {value ? (
        <span>{value}</span>
      ) : placeholder ? (
        <span className="text-muted-foreground/50">{placeholder}</span>
      ) : (
        <span className="text-muted-foreground/30">—</span>
      )}
    </button>
  )
})

// ── Computed row type ───────────────────────────────────────────────────────

interface ComputedRow {
  product: SupplyProduct
  currentAlert: AlertLevel
  blockResults: SupplyBlockResult[]
  suggestedQtys: number[]
}

// ── Main component ──────────────────────────────────────────────────────────

export function SupplyProductTable() {
  const products = useSupplyStore((s) => s.products)
  const entity = useSupplyStore((s) => s.entity)
  const settings = useSupplyStore((s) => s.settings)
  const getBlocks = useSupplyStore((s) => s.getBlocks)
  const setItemQuantity = useSupplyStore((s) => s.setItemQuantity)

  const activeSettings = settings[entity]
  const blocks = useMemo(() => getBlocks(), [getBlocks])

  // Compute supply chain for all products
  const rows: ComputedRow[] = useMemo(() => {
    return products.map((product) => {
      const blockResults = calcSupplyChain(product, blocks, activeSettings)
      const currentAlert = getAlertLevel(product.sufficient_days, activeSettings)

      const suggestedQtys = blocks.map((block, i) => {
        const prevSufficientUntil =
          i === 0
            ? product.sufficient_until
            : blockResults[i - 1]?.sufficient_until ?? null
        return calcSuggestedQty(product, activeSettings, prevSufficientUntil, block.order.delivery_date)
      })

      return { product, currentAlert, blockResults, suggestedQtys }
    })
  }, [products, blocks, activeSettings])

  const handleSave = useCallback(
    (orderId: string, barcode: string, quantity: number) => {
      setItemQuantity(orderId, barcode, quantity)
    },
    [setItemQuantity],
  )

  // ── Block column width ──────────────────────────────────────────────────

  const blockColW = "w-[140px] min-w-[140px]"
  const subColW = "w-[70px] min-w-[70px]"

  return (
    <div className="flex border rounded-lg overflow-hidden bg-background">
      {/* ── Frozen left ─────────────────────────────────────────────── */}
      <div className="min-w-[420px] shrink-0 border-r z-10 bg-background">
        {/* Header */}
        <div className="flex h-10 border-b bg-muted/50 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <div className="w-[120px] min-w-[120px] px-2 flex items-center">Артикул</div>
          <div className="w-[100px] min-w-[100px] px-2 flex items-center">Модель</div>
          <div className="w-[80px] min-w-[80px] px-2 flex items-center">Цвет</div>
          <div className="w-[50px] min-w-[50px] px-2 flex items-center justify-center">Разм</div>
          <div className="w-[70px] min-w-[70px] border-l" />
        </div>
        {/* Sub-header for current stock */}
        <div className="flex h-8 border-b bg-muted/30 text-xs text-muted-foreground">
          <div className="w-[120px] min-w-[120px]" />
          <div className="w-[100px] min-w-[100px]" />
          <div className="w-[80px] min-w-[80px]" />
          <div className="w-[50px] min-w-[50px]" />
          <div className="w-[70px] min-w-[70px] border-l flex">
            <div className="flex-1 flex items-center justify-center border-r" title="Заказов в день">Зак/д</div>
          </div>
        </div>

        {/* Product rows */}
        {rows.map((row, idx) => {
          const p = row.product
          return (
            <div
              key={p.barcode}
              className={`flex h-9 border-b text-sm ${idx % 2 === 0 ? "" : "bg-muted/30"}`}
            >
              <div className="w-[120px] min-w-[120px] px-2 flex items-center truncate" title={p.artikul}>
                <span className="truncate font-mono text-xs">{p.artikul}</span>
              </div>
              <div className="w-[100px] min-w-[100px] px-2 flex items-center truncate" title={p.model_name}>
                <span className="truncate">{p.model}</span>
              </div>
              <div className="w-[80px] min-w-[80px] px-2 flex items-center gap-1.5 truncate" title={p.color}>
                {p.color_code && (
                  <span
                    className="inline-block w-3 h-3 rounded-full border border-black/10 shrink-0"
                    style={{ backgroundColor: p.color_code }}
                  />
                )}
                <span className="truncate text-xs">{p.color}</span>
              </div>
              <div className="w-[50px] min-w-[50px] px-2 flex items-center justify-center tabular-nums">
                {p.size}
              </div>
              <div className="w-[70px] min-w-[70px] border-l flex">
                <div className="flex-1 flex items-center justify-center tabular-nums text-xs">
                  {p.daily_orders ? p.daily_orders.toFixed(1) : "—"}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Scrollable right ────────────────────────────────────────── */}
      <div className="overflow-x-auto flex-1">
        {/* ── Current stock header ──────────────────────────────────── */}
        <div className="flex h-10 border-b bg-muted/50 min-w-max">
          {/* Current stock group */}
          <div className="w-[140px] min-w-[140px] border-r flex items-center justify-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Текущий остаток
          </div>

          {/* Block headers */}
          {blocks.map((block) => (
            <div
              key={block.order.id}
              className={`${blockColW} border-r flex flex-col items-center justify-center px-1`}
            >
              <span className="text-xs font-medium truncate max-w-full" title={block.order.name}>
                {block.order.name}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full mt-0.5 ${statusColor(block.order.status)}`}>
                {statusLabel(block.order.status)}
              </span>
            </div>
          ))}
        </div>

        {/* ── Sub-headers ───────────────────────────────────────────── */}
        <div className="flex h-8 border-b bg-muted/30 min-w-max text-xs text-muted-foreground">
          {/* Current stock sub-cols */}
          <div className="w-[70px] min-w-[70px] flex items-center justify-center border-r" title="Остаток общий">
            Ост
          </div>
          <div className="w-[70px] min-w-[70px] flex items-center justify-center border-r" title="Дней достаточности">
            Дн
          </div>

          {/* Block sub-cols */}
          {blocks.map((block) => (
            <div key={block.order.id} className={`${blockColW} border-r flex`}>
              <div className={`${subColW} flex items-center justify-center border-r`} title="К заказу">
                Кол
              </div>
              <div className={`${subColW} flex items-center justify-center`} title="Дней достаточности">
                Дн
              </div>
            </div>
          ))}
        </div>

        {/* ── Data rows ─────────────────────────────────────────────── */}
        {rows.map((row, idx) => {
          const p = row.product
          const currentDaysAlert = row.currentAlert

          return (
            <div
              key={p.barcode}
              className={`flex h-9 border-b text-sm min-w-max ${idx % 2 === 0 ? "" : "bg-muted/30"}`}
            >
              {/* Current stock */}
              <div className="w-[70px] min-w-[70px] flex items-center justify-center tabular-nums border-r text-xs">
                {p.stock_total ?? "—"}
              </div>
              <div
                className={`w-[70px] min-w-[70px] flex items-center justify-center tabular-nums border-r text-xs gap-1 ${alertBg(currentDaysAlert)}`}
              >
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${alertDot(currentDaysAlert)}`}
                />
                {p.sufficient_days !== null ? p.sufficient_days : "—"}
              </div>

              {/* Block cells */}
              {blocks.map((block, bi) => {
                const result = row.blockResults[bi]
                const suggested = row.suggestedQtys[bi] ?? 0
                const qty = result?.quantity ?? 0
                const isDraft = block.order.status === "draft"
                const blockAlert = result?.alert_level ?? "ok"

                return (
                  <div key={block.order.id} className={`${blockColW} border-r flex`}>
                    {/* Quantity (editable) */}
                    <div className={`${subColW} flex items-center justify-center border-r px-0.5`}>
                      <EditableCell
                        value={qty}
                        placeholder={suggested}
                        orderId={block.order.id}
                        barcode={p.barcode}
                        disabled={!isDraft}
                        onSave={handleSave}
                      />
                    </div>
                    {/* Sufficient days */}
                    <div
                      className={`${subColW} flex items-center justify-center tabular-nums text-xs gap-1 ${alertBg(blockAlert)}`}
                    >
                      {result?.sufficient_days !== null && result?.sufficient_days !== undefined ? (
                        <>
                          <span
                            className={`inline-block w-1.5 h-1.5 rounded-full ${alertDot(blockAlert)}`}
                          />
                          {result.sufficient_days}
                        </>
                      ) : (
                        "—"
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}

        {/* Empty state */}
        {rows.length === 0 && (
          <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
            Нет товаров для отображения
          </div>
        )}
      </div>
    </div>
  )
}
