import { useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Trash2, Edit3, X, Check, Sparkles } from "lucide-react"
import {
  fetchSkleykaDetail,
  fetchSkleykaHistory,
  bulkUnlinkTovaryFromSkleyka,
  deleteSkleyka,
  updateSkleyka,
  type AuditEntry,
  type SkleykaDetailSKU,
} from "@/lib/catalog/service"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { CellText } from "@/components/catalog/ui/cell-text"
import { colorSwatchStyle, relativeDate } from "@/lib/catalog/color-utils"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"
import { compareRazmer } from "@/lib/catalog/size-utils"

const MAX_SKU = 30

function ColorSwatch({ hex, size = 14 }: { hex: string | null | undefined; size?: number }) {
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ ...colorSwatchStyle(hex), width: size, height: size }}
    />
  )
}

function ChannelBadge({ channel }: { channel: "wb" | "ozon" }) {
  if (channel === "wb") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-pink-50 text-pink-700 ring-1 ring-inset ring-pink-600/20">
        <span className="w-1.5 h-1.5 rounded-full bg-pink-500" />
        Wildberries
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20">
      <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
      Ozon
    </span>
  )
}

function SidebarBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="text-xs uppercase tracking-wider text-stone-400 mb-3">{title}</div>
      {children}
    </div>
  )
}

type Tab = "sku" | "analytics" | "history"

// ─── W10.25 + W10.36 — История склейки (audit_log) ────────────────────────
//
// Read-only лента изменений по `audit_log`: сама склейка + её junction
// (`tovary_skleyki_*`, `artikuly_skleyki_*`). Сделано по образцу TabHistory
// из `model-card.tsx`.

function skleykaActionBadgeClass(action: AuditEntry["action"]): string {
  switch (action) {
    case "INSERT":
      return "bg-emerald-100 text-emerald-700 border-emerald-200"
    case "UPDATE":
      return "bg-blue-100 text-blue-700 border-blue-200"
    case "DELETE":
      return "bg-red-100 text-red-700 border-red-200"
  }
}

function skleykaTableLabel(t: string): string {
  switch (t) {
    case "skleyki_wb":
    case "skleyki_ozon":
      return "Склейка"
    case "tovary_skleyki_wb":
    case "tovary_skleyki_ozon":
      return "Привязка SKU"
    case "artikuly_skleyki_wb":
    case "artikuly_skleyki_ozon":
      return "Привязка артикула"
    default:
      return t
  }
}

function formatAuditValue(v: unknown): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "string") return v.length > 80 ? v.slice(0, 80) + "…" : v
  if (typeof v === "number" || typeof v === "boolean") return String(v)
  try {
    const json = JSON.stringify(v)
    return json.length > 80 ? json.slice(0, 80) + "…" : json
  } catch {
    return String(v)
  }
}

function formatAuditDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}

function shortUser(uid: string | null): string {
  if (!uid) return "system"
  return uid.slice(0, 8)
}

function SkleykaHistoryTab({ id, channel }: { id: number; channel: "wb" | "ozon" }) {
  const { data, isLoading, error } = useQuery<AuditEntry[]>({
    queryKey: ["skleyka-history", id, channel],
    queryFn: () => fetchSkleykaHistory(id, channel, 200),
    staleTime: 30 * 1000,
  })

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-stone-200 p-8 text-center text-sm text-stone-400">
        Загружаем историю…
      </div>
    )
  }
  if (error) {
    return (
      <div className="bg-white rounded-lg border border-stone-200 p-8 text-center text-sm text-red-600">
        Не удалось загрузить историю: {String(error)}
      </div>
    )
  }

  const rows = data ?? []
  if (rows.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-stone-200 p-8 text-center">
        <div className="text-sm text-stone-700 font-medium">История изменений</div>
        <div className="text-xs text-stone-500 mt-1">
          Изменений пока нет. Журнал ведётся автоматически.
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 space-y-2">
      <div className="px-1 pb-1 flex items-baseline justify-between">
        <div className="font-medium text-stone-900 text-sm">История изменений</div>
        <div className="text-[11px] text-stone-400 uppercase tracking-wider">
          Последние {rows.length}
        </div>
      </div>
      {rows.map((r) => (
        <div key={r.id} className="border border-stone-200 rounded-md p-3 bg-stone-50">
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span
              className={
                "px-1.5 py-0.5 rounded border font-medium uppercase tracking-wider " +
                skleykaActionBadgeClass(r.action)
              }
            >
              {r.action}
            </span>
            <span className="font-medium text-stone-800">
              {skleykaTableLabel(r.table_name)}
            </span>
            <span className="text-stone-400">·</span>
            <span className="text-stone-500 tabular-nums">{formatAuditDate(r.created_at)}</span>
            <span className="text-stone-400">·</span>
            <span
              className="text-stone-500 font-mono"
              title={r.user_id ?? "service_role / system"}
            >
              {shortUser(r.user_id)}
            </span>
          </div>

          {r.action === "INSERT" && (
            <div className="mt-2 text-xs text-stone-600">
              Запись создана{r.row_id ? ` (id=${r.row_id}).` : "."}
            </div>
          )}

          {r.action === "DELETE" && r.before && (
            <div className="mt-2 text-xs text-stone-600">
              <div className="text-stone-500 mb-1">Удалено. Снимок до удаления:</div>
              <div className="grid grid-cols-1 gap-0.5 font-mono text-[11px] text-stone-700">
                {Object.entries(r.before)
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div key={k} className="truncate">
                      <span className="text-stone-500">{k}:</span> {formatAuditValue(v)}
                    </div>
                  ))}
                {Object.keys(r.before).length > 8 && (
                  <div className="text-stone-400">
                    … ещё {Object.keys(r.before).length - 8} полей
                  </div>
                )}
              </div>
            </div>
          )}

          {r.action === "UPDATE" && r.changed && (
            <div className="mt-2 space-y-1 font-mono text-[11px]">
              {Object.entries(r.changed).map(([key, diff]) => (
                <div key={key} className="flex flex-wrap gap-1 items-baseline">
                  <span className="text-stone-700 font-medium">{key}:</span>
                  <span className="text-red-600 line-through">{formatAuditValue(diff.from)}</span>
                  <span className="text-stone-400">→</span>
                  <span className="text-emerald-700">{formatAuditValue(diff.to)}</span>
                </div>
              ))}
              {Object.keys(r.changed).length === 0 && (
                <div className="text-stone-400 italic">изменено (без полевых изменений)</div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

interface SkleykaCardProps {
  id: number
  channel: "wb" | "ozon"
  onBack: () => void
}

export function SkleykaCard({ id, channel, onBack }: SkleykaCardProps) {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["skleyka-detail", id, channel],
    queryFn: () => fetchSkleykaDetail(id, channel),
    staleTime: 60 * 1000,
  })

  const [tab, setTab] = useState<Tab>("sku")
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editingName, setEditingName] = useState(false)
  const [draftName, setDraftName] = useState("")
  const [busy, setBusy] = useState(false)

  const skuCount = data?.tovary.length ?? 0
  const fraction = Math.min(skuCount / MAX_SKU, 1)
  const isOverflow = skuCount > MAX_SKU

  // W10.29 — стабильный физический порядок: artikul → cvet → размер. Не
  // зависит от статусов: смена статуса не должна менять порядок строк.
  const sortedTovary = useMemo(() => {
    const rows = data?.tovary ?? []
    return [...rows].sort((a, b) => {
      const artCmp = (a.artikul ?? "").localeCompare(b.artikul ?? "", "ru", { numeric: true })
      if (artCmp !== 0) return artCmp
      const cvetCmp = (a.cvet_color_code ?? "").localeCompare(b.cvet_color_code ?? "", "ru", { numeric: true })
      if (cvetCmp !== 0) return cvetCmp
      return compareRazmer(a.razmer ?? null, b.razmer ?? null)
    })
  }, [data])

  // W10.23 — группировка SKU по `artikul_id`. Заголовок: «<артикул>/<цвет> · N SKU (S, M, L)».
  // Внутри группы — те же поля, но размеры уже отсортированы через compareRazmer.
  const artikulGroups = useMemo(() => {
    const groups = new Map<string, { key: string; sortKey: string; sku: SkleykaDetailSKU[] }>()
    for (const row of sortedTovary) {
      // Если artikul_id отсутствует (теоретически у legacy-данных) — fallback
      // на сам артикул-строку, чтобы такие SKU всё равно сгруппировались.
      const key = row.artikul_id != null ? `id:${row.artikul_id}` : `art:${row.artikul ?? row.tovar_id}`
      const sortKey = (row.artikul ?? "") + "|" + (row.cvet_color_code ?? "")
      const bucket = groups.get(key)
      if (bucket) {
        bucket.sku.push(row)
      } else {
        groups.set(key, { key, sortKey, sku: [row] })
      }
    }
    const arr = Array.from(groups.values())
    arr.sort((a, b) => a.sortKey.localeCompare(b.sortKey, "ru", { numeric: true }))
    for (const g of arr) {
      g.sku.sort((a, b) => compareRazmer(a.razmer ?? null, b.razmer ?? null))
    }
    return arr
  }, [sortedTovary])

  const allBarkods = useMemo(() => sortedTovary.map((t) => t.barkod), [sortedTovary])
  const allSelected = allBarkods.length > 0 && selected.size === allBarkods.length

  const toggleAll = () => {
    if (allSelected) setSelected(new Set())
    else setSelected(new Set(allBarkods))
  }
  const toggleOne = (b: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(b)) next.delete(b)
      else next.add(b)
      return next
    })
  }

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["skleyka-detail", id, channel] })
    qc.invalidateQueries({ queryKey: [`skleyki-${channel}`, "with-counts"] })
    qc.invalidateQueries({ queryKey: ["catalog-counts"] })
  }

  const handleUnlinkOne = async (barkod: string) => {
    if (busy) return
    setBusy(true)
    try {
      await bulkUnlinkTovaryFromSkleyka([barkod], channel)
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(barkod)
        return next
      })
      invalidate()
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setBusy(false)
    }
  }

  const handleBulkUnlink = async () => {
    if (busy || selected.size === 0) return
    if (!confirm(`Отвязать ${selected.size} SKU от склейки?`)) return
    setBusy(true)
    try {
      await bulkUnlinkTovaryFromSkleyka(Array.from(selected), channel)
      setSelected(new Set())
      invalidate()
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setBusy(false)
    }
  }

  const handleDeleteSkleyka = async () => {
    if (busy) return
    if (!data) return
    if (!confirm(
      `Удалить склейку «${data.nazvanie}»? ${skuCount > 0
        ? `Это отвяжет ${skuCount} SKU. Сами SKU останутся.`
        : ""}`,
    )) return
    setBusy(true)
    try {
      await deleteSkleyka(id, channel)
      qc.invalidateQueries({ queryKey: [`skleyki-${channel}`, "with-counts"] })
      qc.invalidateQueries({ queryKey: ["catalog-counts"] })
      onBack()
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setBusy(false)
    }
  }

  const startEdit = () => {
    setDraftName(data?.nazvanie ?? "")
    setEditingName(true)
  }
  const saveEdit = async () => {
    const name = draftName.trim()
    if (!name || name === data?.nazvanie) {
      setEditingName(false)
      return
    }
    setBusy(true)
    try {
      await updateSkleyka(id, channel, { nazvanie: name })
      invalidate()
      setEditingName(false)
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setBusy(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-stone-400">
        Загрузка склейки…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-red-500">
        Ошибка загрузки склейки
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="p-1.5 hover:bg-stone-100 rounded-md"
            aria-label="Назад"
          >
            <ArrowLeft className="w-4 h-4 text-stone-700" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1 flex items-center gap-2">
              Склейка
              <ChannelBadge channel={channel} />
              {data.importer_nazvanie && (
                <span className="text-stone-500 normal-case tracking-normal">
                  · {data.importer_nazvanie}
                </span>
              )}
            </div>
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  autoFocus
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveEdit()
                    if (e.key === "Escape") setEditingName(false)
                  }}
                  className="text-2xl px-2 py-1 border border-stone-300 rounded-md outline-none focus:border-stone-900 cat-font-serif italic"
                />
                <button
                  type="button"
                  onClick={saveEdit}
                  disabled={busy}
                  className="p-1.5 rounded-md bg-stone-900 text-white hover:bg-stone-800 disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setEditingName(false)}
                  className="p-1.5 rounded-md hover:bg-stone-100"
                >
                  <X className="w-4 h-4 text-stone-500" />
                </button>
              </div>
            ) : (
              <h1 className="text-2xl text-stone-900 cat-font-serif italic truncate">
                {data.nazvanie}
              </h1>
            )}
          </div>

          {/* Big completeness ring */}
          <div className="flex items-center gap-2 shrink-0">
            <CompletenessRing value={fraction} size={80} hideLabel />
            <div className="text-right">
              <div className="text-2xl font-medium tabular-nums leading-none text-stone-900">
                {skuCount}
                <span className="text-stone-400 text-base">/{MAX_SKU}</span>
              </div>
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mt-1">
                {isOverflow ? "Переполнена" : skuCount === 0 ? "Пуста" : "Заполненность"}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={startEdit}
              disabled={editingName || busy}
              className="px-2.5 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 disabled:opacity-50"
            >
              <Edit3 className="w-3.5 h-3.5" /> Редактировать
            </button>
            <button
              type="button"
              onClick={handleDeleteSkleyka}
              disabled={busy}
              className="px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-md flex items-center gap-1.5 disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" /> Удалить
            </button>
            <button
              type="button"
              onClick={onBack}
              className="p-1.5 hover:bg-stone-100 rounded-md"
              aria-label="Закрыть"
            >
              <X className="w-4 h-4 text-stone-500" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 -mb-4">
          {(
            [
              { id: "sku", label: `SKU · ${skuCount}` },
              { id: "analytics", label: "Аналитика" },
              { id: "history", label: "История" },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id as Tab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                tab === t.id ? "text-stone-900 font-medium" : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              {tab === t.id && <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />}
            </button>
          ))}
        </div>
      </div>

      {/* Body — content + sidebar */}
      <div className="flex-1 overflow-auto">
        <div className="px-6 py-6 grid grid-cols-3 gap-6 max-w-7xl mx-auto w-full">
          {/* Main column (2/3) */}
          <div className="col-span-2 space-y-4">
            {tab === "sku" && (
              <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-stone-200 flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      className="rounded border-stone-300"
                      style={{ accentColor: "#1C1917" }}
                      aria-label="Выбрать все SKU"
                    />
                    <div className="font-medium text-stone-900">SKU в склейке</div>
                  </div>
                  <div className="text-xs text-stone-500 tabular-nums">
                    {skuCount} {skuCount === 0 ? "(пусто)" : `из ${MAX_SKU}`}
                  </div>
                </div>
                {/* W10.23 — группировка SKU по артикулу. */}
                {data.tovary.length === 0 ? (
                  <div className="px-3 py-8 text-center text-sm text-stone-400 italic">
                    В этой склейке нет SKU. Добавьте их из реестра /catalog/tovary.
                  </div>
                ) : (
                  <div className="divide-y divide-stone-200">
                    {artikulGroups.map((group) => {
                      const head = group.sku[0]
                      const sizes = group.sku
                        .map((s) => s.razmer ?? "—")
                        .filter((s) => s !== "—")
                      const sizesLabel = sizes.length > 0 ? sizes.join(", ") : "—"
                      const colorLabel = head.cvet_color_code ?? head.cvet_nazvanie ?? "—"
                      const artikulKod = head.artikul ?? "—"
                      return (
                        <div key={group.key}>
                          {/* Group header */}
                          <div className="px-4 py-2 bg-stone-50/70 border-b border-stone-200 flex items-center gap-2 text-xs">
                            <ColorSwatch hex={head.cvet_hex} size={14} />
                            <CellText
                              className="font-mono font-medium text-stone-800"
                              title={`${artikulKod} / ${colorLabel}`}
                            >
                              {artikulKod}/{colorLabel}
                            </CellText>
                            <span className="text-stone-400">·</span>
                            <span className="tabular-nums text-stone-600">
                              {group.sku.length} SKU
                            </span>
                            <span className="text-stone-400">·</span>
                            <CellText
                              className="text-stone-500 font-mono"
                              title={sizesLabel}
                            >
                              ({sizesLabel})
                            </CellText>
                          </div>
                          {/* W10.27 — горизонтальный скролл + min-w для SKU-таблицы внутри склейки. */}
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm min-w-[900px]">
                              <thead className="bg-stone-50/40 border-b border-stone-100">
                                <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                                  <th className="px-3 py-1.5 w-8" />
                                  <th className="px-3 py-1.5 font-medium">Баркод</th>
                                  <th className="px-3 py-1.5 font-medium">Артикул</th>
                                  <th className="px-3 py-1.5 font-medium">Модель</th>
                                  <th className="px-3 py-1.5 font-medium">Цвет</th>
                                  <th className="px-3 py-1.5 font-medium">Размер</th>
                                  <th className="px-3 py-1.5 font-medium">
                                    Статус {channel === "wb" ? "WB" : "OZON"}
                                  </th>
                                  <th className="w-10" />
                                </tr>
                              </thead>
                              <tbody>
                                {group.sku.map((t) => {
                                  const isSel = selected.has(t.barkod)
                                  const status = channel === "wb" ? t.status_id : t.status_ozon_id
                                  return (
                                    <tr
                                      key={t.tovar_id}
                                      className={`border-b border-stone-100 last:border-0 group ${
                                        isSel ? "bg-stone-50" : "hover:bg-stone-50/60"
                                      }`}
                                    >
                                      <td className="px-3 py-2">
                                        <input
                                          type="checkbox"
                                          checked={isSel}
                                          onChange={() => toggleOne(t.barkod)}
                                          className="rounded border-stone-300"
                                          style={{ accentColor: "#1C1917" }}
                                        />
                                      </td>
                                      <td className="px-3 py-2">
                                        <CellText className="font-mono text-xs text-stone-700" title={t.barkod}>
                                          {t.barkod}
                                        </CellText>
                                      </td>
                                      <td className="px-3 py-2">
                                        <CellText className="font-mono text-xs text-stone-600" title={t.artikul ?? ""}>
                                          {t.artikul ?? "—"}
                                        </CellText>
                                      </td>
                                      <td className="px-3 py-2">
                                        <CellText className="font-mono text-xs font-medium" title={t.model_osnova_kod ?? ""}>
                                          {t.model_osnova_kod ?? "—"}
                                        </CellText>
                                      </td>
                                      <td className="px-3 py-2">
                                        <div className="flex items-center gap-1.5 min-w-0">
                                          <ColorSwatch hex={t.cvet_hex} size={14} />
                                          <CellText className="font-mono text-xs text-stone-600" title={t.cvet_color_code ?? ""}>
                                            {t.cvet_color_code ?? "—"}
                                          </CellText>
                                          {t.cvet_nazvanie && (
                                            <CellText className="text-stone-500 text-xs" title={t.cvet_nazvanie}>
                                              {t.cvet_nazvanie}
                                            </CellText>
                                          )}
                                        </div>
                                      </td>
                                      <td className="px-3 py-2 font-mono text-xs">{t.razmer ?? "—"}</td>
                                      <td className="px-3 py-2">
                                        <StatusBadge statusId={status ?? 0} compact />
                                      </td>
                                      <td className="px-3 py-2 opacity-0 group-hover:opacity-100">
                                        <button
                                          type="button"
                                          onClick={() => handleUnlinkOne(t.barkod)}
                                          disabled={busy}
                                          title="Отвязать SKU от склейки"
                                          className="p-1 hover:bg-red-50 rounded text-red-600 disabled:opacity-50"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      </td>
                                    </tr>
                                  )
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {tab === "analytics" && (
              <div className="bg-white rounded-lg border border-stone-200 p-8 text-center">
                <div className="text-sm text-stone-700 font-medium">Аналитика склейки</div>
                <div className="text-xs text-stone-500 mt-1">
                  Будет в следующих фазах: продажи, остатки, маржинальность по склейке.
                </div>
              </div>
            )}

            {tab === "history" && <SkleykaHistoryTab id={id} channel={channel} />}
          </div>

          {/* Sidebar (1/3) */}
          <div className="col-span-1 space-y-4">
            <SidebarBlock title="Правила склейки">
              {/* W10.24 — обновлённый текст правил. */}
              <div className="space-y-2 text-sm">
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">До {MAX_SKU} SKU в одной склейке.</span>
                </div>
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">Только Wildberries.</span>
                </div>
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">
                    Один артикул может находиться только в одной активной склейке.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">Группируется по сезону.</span>
                </div>
              </div>
            </SidebarBlock>

            <SidebarBlock title="Что это даёт?">
              <div className="text-sm text-stone-600 leading-relaxed flex gap-2">
                <Sparkles className="w-3.5 h-3.5 mt-0.5 text-amber-500 shrink-0" />
                <span>
                  При публикации все SKU из склейки группируются в одну карточку товара —
                  покупатель видит варианты цвета/размера на одной странице. Это{" "}
                  <span className="font-medium text-stone-800">бустит ранжирование</span>:
                  ранжируются не отдельные SKU, а вся карточка целиком.
                </span>
              </div>
            </SidebarBlock>

            <SidebarBlock title="Метрики">
              <dl className="space-y-2 text-sm">
                <div className="flex items-baseline justify-between">
                  <dt className="text-stone-500 text-xs uppercase tracking-wider">SKU</dt>
                  <dd className="font-medium tabular-nums">
                    {skuCount} / {MAX_SKU}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between">
                  <dt className="text-stone-500 text-xs uppercase tracking-wider">Создана</dt>
                  <dd className="text-stone-700 text-xs">{relativeDate(data.created_at)}</dd>
                </div>
                <div className="flex items-baseline justify-between">
                  <dt className="text-stone-500 text-xs uppercase tracking-wider">Обновлена</dt>
                  <dd className="text-stone-700 text-xs">{relativeDate(data.updated_at)}</dd>
                </div>
              </dl>
            </SidebarBlock>
          </div>
        </div>
      </div>

      {/* Bulk actions bar — sticky bottom on SKU tab */}
      {tab === "sku" && (
        <BulkActionsBar
          selectedCount={selected.size}
          onClear={() => setSelected(new Set())}
          actions={[
            {
              id: "unlink",
              label: "Отвязать от склейки",
              icon: <Trash2 className="w-3.5 h-3.5" />,
              onClick: handleBulkUnlink,
              destructive: true,
              disabled: busy,
            },
          ]}
        />
      )}
    </div>
  )
}
