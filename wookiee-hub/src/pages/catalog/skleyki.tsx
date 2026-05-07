import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Plus, Search, ArrowLeft, AlertTriangle, CheckCircle2 } from "lucide-react"
import { fetchSkleykiWb, fetchSkleykiOzon, fetchSkleykaDetail } from "@/lib/catalog/service"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { relativeDate, swatchColor } from "@/lib/catalog/color-utils"

function ColorSwatch({ colorCode, size = 14 }: { colorCode: string | null; size?: number }) {
  if (!colorCode) return <div className="rounded-full bg-stone-200" style={{ width: size, height: size }} />
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ width: size, height: size, background: swatchColor(colorCode) }}
    />
  )
}

function SkleykaCard({
  id,
  channel,
  onBack,
}: {
  id: number
  channel: "wb" | "ozon"
  onBack: () => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["skleyka-detail", id, channel],
    queryFn: () => fetchSkleykaDetail(id, channel),
    staleTime: 3 * 60 * 1000,
  })

  const maxSku = channel === "ozon" ? 30 : 1
  const skuCount = data?.tovary.length ?? 0
  const isOverLimit = skuCount > maxSku
  const isUnderFilled = channel === "wb" && skuCount !== 1
  const progressPct = channel === "ozon" ? Math.min(skuCount / 30, 1) : skuCount === 1 ? 1 : 0

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-1.5 hover:bg-stone-100 rounded-md">
            <ArrowLeft className="w-4 h-4 text-stone-700" />
          </button>
          <div className="flex-1">
            <div className="text-xs text-stone-400 uppercase tracking-wider mb-0.5">
              Склейка · {channel === "wb" ? "Wildberries" : "Ozon"}
            </div>
            {isLoading ? (
              <div className="h-7 w-48 bg-stone-100 rounded animate-pulse" />
            ) : (
              <h2 className="text-2xl font-medium text-stone-900 cat-font-serif">{data?.nazvanie ?? "—"}</h2>
            )}
            {data?.importer_nazvanie && (
              <div className="text-sm text-stone-500 mt-0.5">{data.importer_nazvanie}</div>
            )}
          </div>
          {!isLoading && data && (
            <div className="flex items-center gap-3">
              {/* Progress */}
              {channel === "ozon" ? (
                <div className="flex items-center gap-2">
                  <div className="w-32 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${isOverLimit ? "bg-red-500" : "bg-emerald-500"}`}
                      style={{ width: `${progressPct * 100}%` }}
                    />
                  </div>
                  <span className={`text-xs tabular-nums font-medium ${isOverLimit ? "text-red-600" : "text-stone-700"}`}>
                    {skuCount}/30 SKU
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  {isUnderFilled ? (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  )}
                  <span className="text-xs text-stone-600">{skuCount} SKU</span>
                  {isUnderFilled && (
                    <span className="text-xs text-amber-600">· WB правило: 1 SKU на склейку</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-6 py-5">
        {isLoading && (
          <div className="text-sm text-stone-400">Загрузка…</div>
        )}
        {error && (
          <div className="text-sm text-red-500">Ошибка загрузки склейки</div>
        )}
        {!isLoading && !error && data && (
          <>
            <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-stone-50/80 border-b border-stone-200">
                  <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                    <th className="px-3 py-2.5 font-medium">#</th>
                    <th className="px-3 py-2.5 font-medium">Баркод</th>
                    <th className="px-3 py-2.5 font-medium">Артикул</th>
                    <th className="px-3 py-2.5 font-medium">Модель</th>
                    <th className="px-3 py-2.5 font-medium">Цвет</th>
                    <th className="px-3 py-2.5 font-medium">Размер</th>
                    <th className="px-3 py-2.5 font-medium border-l border-stone-200">WB</th>
                    <th className="px-3 py-2.5 font-medium">Ozon</th>
                    {channel === "wb" && (
                      <th className="px-3 py-2.5 font-medium">Номенкл. WB</th>
                    )}
                    {channel === "ozon" && (
                      <th className="px-3 py-2.5 font-medium">Арт. OZON</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {data.tovary.map((t, i) => (
                    <tr key={t.tovar_id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                      <td className="px-3 py-2.5 text-xs text-stone-400 tabular-nums">{i + 1}</td>
                      <td className="px-3 py-2.5 font-mono text-xs text-stone-700">{t.barkod}</td>
                      <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{t.artikul ?? "—"}</td>
                      <td className="px-3 py-2.5 font-mono text-xs font-medium text-stone-900">{t.model_osnova_kod ?? "—"}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <ColorSwatch colorCode={t.cvet_color_code} size={14} />
                          <span className="font-mono text-xs text-stone-700">{t.cvet_color_code ?? "—"}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs">{t.razmer ?? "—"}</td>
                      <td className="px-3 py-2.5 border-l border-stone-100">
                        <StatusBadge statusId={t.status_id ?? 0} compact />
                      </td>
                      <td className="px-3 py-2.5">
                        <StatusBadge statusId={t.status_ozon_id ?? 0} compact />
                      </td>
                      {channel === "wb" && (
                        <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500 tabular-nums">
                          {t.nomenklatura_wb ?? "—"}
                        </td>
                      )}
                      {channel === "ozon" && (
                        <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500">
                          {t.artikul_ozon ?? "—"}
                        </td>
                      )}
                    </tr>
                  ))}
                  {data.tovary.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-3 py-6 text-center text-sm text-stone-400 italic">
                        В этой склейке нет SKU
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Rule reminder */}
            <div className={`mt-4 p-4 rounded-lg border text-xs ${
              channel === "wb"
                ? (isUnderFilled ? "bg-amber-50 border-amber-200 text-amber-700" : "bg-emerald-50 border-emerald-200 text-emerald-700")
                : (isOverLimit ? "bg-red-50 border-red-200 text-red-700" : "bg-stone-50 border-stone-200 text-stone-500")
            }`}>
              {channel === "wb"
                ? `Правило WB: 1 SKU на карточку-склейку. В этой склейке: ${skuCount} SKU.`
                : `Лимит OZON: до 30 SKU на карточку. Использовано: ${skuCount}/30.`
              }
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function SkleykiPage() {
  const [tab, setTab] = useState<"wb" | "ozon">("wb")
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedChannel, setSelectedChannel] = useState<"wb" | "ozon">("wb")

  const wbQ = useQuery({ queryKey: ["skleyki-wb"], queryFn: fetchSkleykiWb, staleTime: 5 * 60 * 1000 })
  const ozonQ = useQuery({ queryKey: ["skleyki-ozon"], queryFn: fetchSkleykiOzon, staleTime: 5 * 60 * 1000 })

  const q = tab === "wb" ? wbQ : ozonQ
  const raw = q.data ?? []
  const filtered = search.trim()
    ? raw.filter((s) => s.nazvanie.toLowerCase().includes(search.trim().toLowerCase()))
    : raw

  const TABS = [
    { id: "wb", label: "Wildberries", count: wbQ.data?.length ?? 0, color: "text-violet-700" },
    { id: "ozon", label: "Ozon", count: ozonQ.data?.length ?? 0, color: "text-blue-700" },
  ] as const

  if (selectedId !== null) {
    return (
      <SkleykaCard
        id={selectedId}
        channel={selectedChannel}
        onBack={() => setSelectedId(null)}
      />
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1 className="text-3xl text-stone-900 cat-font-serif">Склейки МП</h1>
            <div className="text-sm text-stone-500 mt-1">
              {(wbQ.data?.length ?? 0) + (ozonQ.data?.length ?? 0)} склеек · WB + Ozon
            </div>
          </div>
          <button className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Новая склейка
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 px-6 shrink-0">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as typeof tab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                tab === t.id ? "text-stone-900 font-medium" : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              {tab === t.id && <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {/* Filter */}
        <div className="flex items-center gap-2 mb-4">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по названию…"
              className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
            />
          </div>
          <div className="ml-auto text-xs text-stone-500 tabular-nums">
            {filtered.length} из {raw.length}
          </div>
        </div>

        {q.isLoading && <div className="text-sm text-stone-400">Загрузка…</div>}
        {q.error && <div className="text-sm text-red-500">Ошибка загрузки</div>}

        {!q.isLoading && !q.error && (
          <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50/80 border-b border-stone-200">
                <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                  <th className="px-3 py-2.5 font-medium w-8">#</th>
                  <th className="px-3 py-2.5 font-medium">Название склейки</th>
                  <th className="px-3 py-2.5 font-medium">Юрлицо</th>
                  <th className="px-3 py-2.5 font-medium">Создано</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <tr
                    key={s.id}
                    className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 cursor-pointer"
                    onClick={() => {
                      setSelectedId(s.id)
                      setSelectedChannel(tab)
                    }}
                  >
                    <td className="px-3 py-3 text-stone-400 tabular-nums text-xs">{i + 1}</td>
                    <td className="px-3 py-3">
                      <div className="font-medium text-stone-900 hover:underline">{s.nazvanie}</div>
                    </td>
                    <td className="px-3 py-3 text-stone-600 text-sm">
                      {s.importer_nazvanie ?? <span className="text-stone-400 italic">—</span>}
                    </td>
                    <td className="px-3 py-3 text-stone-500 text-xs">{relativeDate(s.created_at)}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-sm text-stone-400 italic">
                      Ничего не найдено
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
