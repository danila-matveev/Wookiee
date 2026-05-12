import { useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Trash2, Edit3, X, Check, Sparkles } from "lucide-react"
import {
  fetchSkleykaDetail,
  bulkUnlinkTovaryFromSkleyka,
  deleteSkleyka,
  updateSkleyka,
} from "@/lib/catalog/service"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { translateError } from "@/lib/catalog/error-translator"

const MAX_SKU = 30

function ColorSwatch({ colorCode, size = 14 }: { colorCode: string | null; size?: number }) {
  if (!colorCode) {
    return <div className="rounded-full bg-stone-200" style={{ width: size, height: size }} />
  }
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ width: size, height: size, background: swatchColor(colorCode) }}
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

  const allBarkods = useMemo(() => (data?.tovary.map((t) => t.barkod) ?? []), [data])
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
      alert(translateError(e))
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
      alert(translateError(e))
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
      alert(translateError(e))
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
      alert(translateError(e))
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
                  <div className="font-medium text-stone-900">SKU в склейке</div>
                  <div className="text-xs text-stone-500 tabular-nums">
                    {skuCount} {skuCount === 0 ? "(пусто)" : `из ${MAX_SKU}`}
                  </div>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-stone-50/80 border-b border-stone-200">
                    <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                      <th className="px-3 py-2 w-8">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleAll}
                          className="rounded border-stone-300 align-middle"
                          style={{ accentColor: "#1C1917" }}
                        />
                      </th>
                      <th className="px-3 py-2 font-medium">Баркод</th>
                      <th className="px-3 py-2 font-medium">Артикул</th>
                      <th className="px-3 py-2 font-medium">Модель</th>
                      <th className="px-3 py-2 font-medium">Цвет</th>
                      <th className="px-3 py-2 font-medium">Размер</th>
                      <th className="px-3 py-2 font-medium">
                        Статус {channel === "wb" ? "WB" : "OZON"}
                      </th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.tovary.map((t) => {
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
                            <span className="font-mono text-xs text-stone-700">{t.barkod}</span>
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-stone-600">
                            {t.artikul ?? "—"}
                          </td>
                          <td className="px-3 py-2 font-mono text-xs font-medium">
                            {t.model_osnova_kod ?? "—"}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <ColorSwatch colorCode={t.cvet_color_code} size={14} />
                              <span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span>
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
                    {data.tovary.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-3 py-8 text-center text-sm text-stone-400 italic">
                          В этой склейке нет SKU. Добавьте их из реестра /catalog/tovary.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
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

            {tab === "history" && (
              <div className="bg-white rounded-lg border border-stone-200 p-8 text-center">
                <div className="text-sm text-stone-700 font-medium">История изменений</div>
                <div className="text-xs text-stone-500 mt-1">
                  Будет в следующих фазах: лог добавления/удаления SKU, переименований, операций
                  публикации.
                </div>
              </div>
            )}
          </div>

          {/* Sidebar (1/3) */}
          <div className="col-span-1 space-y-4">
            <SidebarBlock title="Правила склейки">
              <div className="space-y-2 text-sm">
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">Один цвет, разные размеры</span>
                </div>
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">ИЛИ один размер, разные цвета</span>
                </div>
                <div className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="text-stone-700">До {MAX_SKU} SKU в одной склейке</span>
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
