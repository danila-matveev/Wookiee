import { useState, useMemo, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Search, Plus, ArrowLeft, ChevronRight, Edit3 } from "lucide-react"
import {
  fetchCvetaWithUsage, fetchColorDetail,
  type CvetRow,
} from "@/lib/catalog/service"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { swatchColor, relativeDate, SEMEYSTVA } from "@/lib/catalog/color-utils"

function ColorSwatch({ colorCode, size = 20 }: { colorCode: string | null; size?: number }) {
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ width: size, height: size, background: colorCode ? swatchColor(colorCode) : "#e7e5e4" }}
    />
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="font-medium text-stone-900 mb-4">{label}</div>
      {children}
    </div>
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

// ─── Color card ────────────────────────────────────────────────────────────

function ColorCard({ colorId, onBack, onModelClick }: {
  colorId: number
  onBack: () => void
  onModelClick: (id: number) => void
}) {
  const { data: c, isLoading, error } = useQuery({
    queryKey: ["color-detail", colorId],
    queryFn: () => fetchColorDetail(colorId),
    staleTime: 3 * 60 * 1000,
  })

  const modelGroups = useMemo(() => {
    if (!c) return []
    const map = new Map<number, { id: number; kod: string; kategoriya: string | null; tip_kollekcii: string | null; artikuly: typeof c.artikuly }>()
    for (const a of c.artikuly) {
      if (!a.model_osnova_id) continue
      if (!map.has(a.model_osnova_id)) {
        map.set(a.model_osnova_id, {
          id: a.model_osnova_id,
          kod: a.model_osnova_kod ?? "—",
          kategoriya: a.kategoriya,
          tip_kollekcii: a.tip_kollekcii,
          artikuly: [],
        })
      }
      map.get(a.model_osnova_id)!.artikuly.push(a)
    }
    return Array.from(map.values())
  }, [c])

  if (isLoading) return <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">Загрузка…</div>
  if (error || !c) return <div className="flex-1 flex items-center justify-center text-red-500 text-sm">Ошибка загрузки цвета</div>

  const totalSku = c.artikuly.reduce((s, a) => s + a.tovary_cnt, 0)

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4 flex items-center gap-4">
        <button onClick={onBack} className="p-1.5 hover:bg-stone-100 rounded-md">
          <ArrowLeft className="w-4 h-4 text-stone-700" />
        </button>
        <div className="flex-1 flex items-center gap-3">
          <ColorSwatch colorCode={c.color_code} size={40} />
          <div>
            <div className="text-xs text-stone-400">Цвет · семейство {c.semeystvo ?? "—"}</div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-medium text-stone-900 font-mono">{c.color_code}</h2>
              {c.cvet && <span className="text-stone-500">{c.cvet}</span>}
              {c.color && <span className="text-stone-400 text-sm">{c.color}</span>}
              <StatusBadge statusId={c.status_id ?? 0} compact />
            </div>
          </div>
        </div>
        <button className="px-3 py-1.5 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5">
          <Edit3 className="w-3.5 h-3.5" /> Редактировать
        </button>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6 grid grid-cols-3 gap-6 max-w-7xl mx-auto w-full">
        <div className="col-span-2 space-y-4">
          <Section label={`Модели использующие этот цвет (${modelGroups.length})`}>
            {modelGroups.length === 0 ? (
              <div className="text-sm text-stone-400 italic">Цвет не используется ни в одной модели</div>
            ) : (
              <div className="space-y-2">
                {modelGroups.map((mg) => (
                  <button
                    key={mg.id}
                    onClick={() => onModelClick(mg.id)}
                    className="w-full flex items-center justify-between p-3 bg-stone-50 hover:bg-stone-100 rounded-md text-left"
                  >
                    <div>
                      <div className="font-medium text-stone-900 font-mono">{mg.kod}</div>
                      <div className="text-xs text-stone-500">{mg.kategoriya ?? "—"} · {mg.tip_kollekcii ?? "—"}</div>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-stone-600">
                      <span><span className="font-medium">{mg.artikuly.length}</span> арт.</span>
                      <span><span className="font-medium">{mg.artikuly.reduce((s, a) => s + a.tovary_cnt, 0)}</span> SKU</span>
                      <ChevronRight className="w-3.5 h-3.5 text-stone-400" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Section>

          <Section label={`Артикулы (${c.artikuly.length})`}>
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="py-1.5 font-medium">Артикул</th>
                  <th className="py-1.5 font-medium">Модель</th>
                  <th className="py-1.5 font-medium">Вариация</th>
                  <th className="py-1.5 font-medium">WB номенкл.</th>
                  <th className="py-1.5 font-medium text-right">SKU</th>
                </tr>
              </thead>
              <tbody>
                {c.artikuly.map((a) => (
                  <tr key={a.id} className="border-t border-stone-100">
                    <td className="py-2 font-mono text-xs">{a.artikul}</td>
                    <td className="py-2 font-mono text-xs font-medium">{a.model_osnova_kod ?? "—"}</td>
                    <td className="py-2 font-mono text-xs text-stone-500">{a.model_kod ?? "—"}</td>
                    <td className="py-2 font-mono text-[11px] text-stone-500 tabular-nums">{a.nomenklatura_wb ?? "—"}</td>
                    <td className="py-2 text-right tabular-nums text-stone-700">{a.tovary_cnt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        </div>

        <div className="col-span-1 space-y-4">
          <SidebarBlock title="Цвет">
            <div className="flex items-center gap-3">
              <div className="w-16 h-16 rounded-md ring-1 ring-stone-200 shrink-0" style={{ background: swatchColor(c.color_code) }} />
              <div>
                <div className="font-mono text-stone-900">{c.color_code}</div>
                {c.cvet && <div className="text-sm text-stone-600 mt-1">{c.cvet}</div>}
                {c.color && <div className="text-sm text-stone-400">{c.color}</div>}
                {c.lastovica && <div className="text-xs text-stone-500 mt-1">Ластовица: {c.lastovica}</div>}
              </div>
            </div>
          </SidebarBlock>

          <SidebarBlock title="Использование">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-stone-500">Моделей</span><span className="font-medium tabular-nums">{c.modeli_cnt}</span></div>
              <div className="flex justify-between"><span className="text-stone-500">Артикулов</span><span className="font-medium tabular-nums">{c.artikuly_cnt}</span></div>
              <div className="flex justify-between"><span className="text-stone-500">SKU</span><span className="font-medium tabular-nums">{totalSku}</span></div>
            </div>
          </SidebarBlock>

          <SidebarBlock title="Семейство">
            <div className="text-sm text-stone-900">{SEMEYSTVA.find((s) => s.kod === c.semeystvo)?.nazvanie ?? c.semeystvo ?? "—"}</div>
            <div className="text-xs text-stone-400 mt-1">Обновлено: {relativeDate(c.updated_at)}</div>
          </SidebarBlock>
        </div>
      </div>
    </div>
  )
}

// ─── Colors list ───────────────────────────────────────────────────────────

function ColorFamilyTable({ title, items, onOpen }: { title: string; items: CvetRow[]; onOpen: (id: number) => void }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-2">
        {title} <span className="text-stone-300">·</span> <span className="tabular-nums">{items.length}</span>
      </div>
      <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2 font-medium w-10" />
              <th className="px-3 py-2 font-medium">Color Code</th>
              <th className="px-3 py-2 font-medium">Цвет RU</th>
              <th className="px-3 py-2 font-medium">Color EN</th>
              <th className="px-3 py-2 font-medium">Ластовица</th>
              <th className="px-3 py-2 font-medium">Используется в</th>
              <th className="px-3 py-2 font-medium">Статус</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} onClick={() => onOpen(c.id)} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 cursor-pointer">
                <td className="px-3 py-2"><ColorSwatch colorCode={c.color_code} size={20} /></td>
                <td className="px-3 py-2"><span className="font-mono text-stone-900">{c.color_code}</span></td>
                <td className="px-3 py-2">{c.cvet ?? "—"}</td>
                <td className="px-3 py-2 text-stone-500">{c.color ?? "—"}</td>
                <td className="px-3 py-2 text-stone-500">{c.lastovica ?? "—"}</td>
                <td className="px-3 py-2 text-stone-600">
                  {c.modeli_cnt > 0 || c.artikuly_cnt > 0 ? (
                    <span><span className="font-medium text-stone-900">{c.modeli_cnt}</span> мод. · <span className="font-medium">{c.artikuly_cnt}</span> арт.</span>
                  ) : (
                    <span className="text-stone-400 italic text-xs">не используется</span>
                  )}
                </td>
                <td className="px-3 py-2"><StatusBadge statusId={c.status_id ?? 0} compact /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ColorsList({ onOpen }: { onOpen: (id: number) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cveta-with-usage"],
    queryFn: fetchCvetaWithUsage,
    staleTime: 3 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [familyFilter, setFamilyFilter] = useState("all")

  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (familyFilter !== "all") res = res.filter((c) => c.semeystvo === familyFilter)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter((c) => c.color_code.toLowerCase().includes(q) || (c.cvet ?? "").toLowerCase().includes(q) || (c.color ?? "").toLowerCase().includes(q))
    }
    return res
  }, [data, familyFilter, search])

  const knownFamilyCodes = new Set(SEMEYSTVA.map((s) => s.kod))
  const grouped = SEMEYSTVA.map((s) => ({ family: s, items: filtered.filter((c) => c.semeystvo === s.kod) })).filter((g) => g.items.length > 0)
  const ungrouped = filtered.filter((c) => !c.semeystvo || !knownFamilyCodes.has(c.semeystvo))

  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  if (error) return <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки цветов</div>

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1 className="text-3xl text-stone-900 cat-font-serif">Цвета</h1>
            <div className="text-sm text-stone-500 mt-1">{data?.length ?? 0} цветов · группировка по семейству</div>
          </div>
          <button className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Новый цвет
          </button>
        </div>
      </div>
      <div className="px-6 pb-3 flex items-center gap-2 shrink-0 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Поиск по коду или названию…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72" />
        </div>
        <span className="text-xs text-stone-500 mx-1">Семейство:</span>
        {[{ kod: "all", nazvanie: "Все" }, ...SEMEYSTVA].map((s) => (
          <button key={s.kod} onClick={() => setFamilyFilter(s.kod)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${familyFilter === s.kod ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}>
            {s.nazvanie}
          </button>
        ))}
        <div className="ml-auto text-xs text-stone-500 tabular-nums">{filtered.length} из {data?.length ?? 0}</div>
      </div>
      <div className="flex-1 overflow-auto px-6 pb-6 space-y-6">
        {grouped.map((g) => <ColorFamilyTable key={g.family.kod} title={g.family.nazvanie} items={g.items} onOpen={onOpen} />)}
        {ungrouped.length > 0 && <ColorFamilyTable title="Прочие" items={ungrouped} onOpen={onOpen} />}
        {filtered.length === 0 && <div className="py-8 text-center text-sm text-stone-400 italic">Ничего не найдено</div>}
      </div>
    </div>
  )
}

// ─── ColorsPage ────────────────────────────────────────────────────────────

export function ColorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const colorIdParam = searchParams.get("id")
  const colorId = colorIdParam ? Number(colorIdParam) : null

  const openColor = useCallback((id: number) => setSearchParams({ id: String(id) }), [setSearchParams])
  const closeColor = useCallback(() => setSearchParams({}), [setSearchParams])
  const openModel = useCallback((id: number) => { window.location.href = `/catalog/matrix?id=${id}` }, [])

  if (colorId) return <ColorCard colorId={colorId} onBack={closeColor} onModelClick={openModel} />
  return <ColorsList onOpen={openColor} />
}
