import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Archive, Building2, ChevronDown, ChevronRight, Copy, Download, Edit3, Info, MoreHorizontal, Plus, Search } from "lucide-react"
import { archiveModel, bulkUpdateModelStatus, createModel, duplicateModel, fetchArtikulyRegistry, fetchKategorii, fetchKollekcii, fetchMatrixList, fetchStatusy, fetchTovaryRegistry, getUiPref, setUiPref } from "@/lib/catalog/service"
import type { MatrixRow } from "@/lib/catalog/service"
import { StatusBadge, CATALOG_STATUSES } from "@/components/catalog/ui/status-badge"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { Tooltip } from "@/components/catalog/ui/tooltip"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
// Standard razmer chip-pill ladder used in the table.
const RAZMER_LADDER = ["XS", "S", "M", "L", "XL", "XXL"] as const
// ─── Shared helpers ────────────────────────────────────────────────────────
function ColorSwatch({ colorCode, size = 16 }: { colorCode: string | null; size?: number }) {
  if (!colorCode) return <div className="rounded-full bg-stone-200" style={{ width: size, height: size }} />
  return <div className="rounded-full ring-1 ring-stone-200 shrink-0" style={{ width: size, height: size, background: swatchColor(colorCode) }} />
}
function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72" />
    </div>
  )
}
function toggleSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}
type ChipValue = string | number
type ChipItem<T extends ChipValue> = { key: string; value: T; label: string; count?: number }
function FilterChips<T extends ChipValue>({ title, items, selected, onChange, className = "mb-2" }: { title: string; items: ChipItem<T>[]; selected: Set<T>; onChange: (next: Set<T>) => void; className?: string }) {
  if (items.length === 0) return null
  return (
    <div className={`flex items-center gap-1.5 ${className} flex-wrap`}>
      <span className="text-[10px] uppercase tracking-wider text-stone-400 mr-1">{title}</span>
      {items.map((item) => {
        const active = selected.has(item.value)
        return (
          <button key={item.key} onClick={() => onChange(toggleSet(selected, item.value))} className={`px-2.5 py-1 text-xs rounded-md transition-colors ${item.count == null ? "" : "flex items-center gap-1.5"} ${active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 border border-stone-200"}`}>
            <span>{item.label}</span>
            {item.count != null && <span className={`text-[10px] tabular-nums ${active ? "text-stone-300" : "text-stone-400"}`}>{item.count}</span>}
          </button>
        )
      })}
      {selected.size > 0 && <button onClick={() => onChange(new Set())} className="text-[11px] text-stone-500 hover:text-stone-800 underline ml-1">сбросить</button>}
    </div>
  )
}
// ─── Matrix list view (Базовые модели) — Wave 2 B1 ─────────────────────────
type GroupBy = "none" | "kategoriya" | "kollekciya" | "fabrika" | "status"
type ListTab = "modeli_osnova" | "artikuly" | "tovary"
type StatusOption = { id: number; nazvanie: string; tip: string; color: string | null }
const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "none", label: "Без группировки" },
  { value: "kategoriya", label: "По категории" },
  { value: "kollekciya", label: "По коллекции" },
  { value: "fabrika", label: "По фабрике" },
  { value: "status", label: "По статусу" },
]
const MODEL_COLUMNS = [
  ["Название"], ["Категория"], ["Коллекция"], ["Фабрика"], ["Статус"], ["Размеры"], ["Цвета"], ["Заполн."],
  ["Цв / Арт / SKU", "text-right"], ["Обновлено"],
] as const
function getGroupKey(row: MatrixRow, groupBy: GroupBy, statusNameById: Map<number, string>): string {
  switch (groupBy) {
    case "kategoriya": return row.kategoriya ?? "Без категории"
    case "kollekciya": return row.kollekciya ?? "Без коллекции"
    case "fabrika": return row.fabrika ?? "Без фабрики"
    case "status": return row.status_id != null ? (statusNameById.get(row.status_id) ?? `Статус #${row.status_id}`) : "Без статуса"
    default: return ""
  }
}
function modelMatches(row: MatrixRow, query: string) {
  if (row.kod.toLowerCase().includes(query) || (row.nazvanie_sayt ?? "").toLowerCase().includes(query)) return true
  return row.modeli.some((v) =>
    (v.kod ?? "").toLowerCase().includes(query) ||
    (v.nazvanie ?? "").toLowerCase().includes(query) ||
    (v.artikul_modeli ?? "").toLowerCase().includes(query)
  )
}
function ModeliOsnovaTable({ rows, kategorii, kollekcii, modelStatuses, onOpen }: { rows: MatrixRow[]; kategorii: { id: number; nazvanie: string }[]; kollekcii: { id: number; nazvanie: string }[]; modelStatuses: StatusOption[]; onOpen: (kod: string) => void }) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<number>>(new Set())
  const [selectedCollectionNames, setSelectedCollectionNames] = useState<Set<string>>(new Set())
  const [selectedStatusIds, setSelectedStatusIds] = useState<Set<number>>(new Set())
  const [incompleteOnly, setIncompleteOnly] = useState(false)
  const [groupBy, setGroupBy] = useState<GroupBy>("none")
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [selectedKods, setSelectedKods] = useState<Set<string>>(new Set())
  const [openMenuKod, setOpenMenuKod] = useState<string | null>(null)
  const [bulkStatusOpen, setBulkStatusOpen] = useState(false)
  const groupByLoadedRef = useRef(false)
  // Load groupBy preference once
  useEffect(() => {
    if (groupByLoadedRef.current) return
    groupByLoadedRef.current = true
    getUiPref<GroupBy>("matrix", "groupBy").then((v) => { if (v && GROUP_BY_OPTIONS.some((o) => o.value === v)) setGroupBy(v) }).catch(() => { /* ignore — default is fine */ })
  }, [])
  // Persist groupBy whenever it changes
  useEffect(() => {
    if (groupByLoadedRef.current) setUiPref("matrix", "groupBy", groupBy).catch(() => { /* non-fatal */ })
  }, [groupBy])
  // Close more-menu / bulk-status dropdown when clicking elsewhere
  useEffect(() => {
    if (!openMenuKod && !bulkStatusOpen) return
    const onDocClick = () => { setOpenMenuKod(null); setBulkStatusOpen(false) }
    document.addEventListener("click", onDocClick)
    return () => document.removeEventListener("click", onDocClick)
  }, [openMenuKod, bulkStatusOpen])
  const statusNameById = useMemo(() => new Map(modelStatuses.map((s) => [s.id, s.nazvanie])), [modelStatuses])
  // Status counts (from full rows, not filtered) for chip badges
  const statusCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const r of rows) if (r.status_id != null) acc.set(r.status_id, (acc.get(r.status_id) ?? 0) + 1)
    return acc
  }, [rows])
  const filtered = useMemo(() => {
    let res = rows
    if (selectedStatusIds.size > 0) res = res.filter((r) => r.status_id != null && selectedStatusIds.has(r.status_id))
    if (selectedCategoryIds.size > 0) res = res.filter((r) => r.kategoriya_id != null && selectedCategoryIds.has(r.kategoriya_id))
    if (selectedCollectionNames.size > 0) res = res.filter((r) => r.kollekciya != null && selectedCollectionNames.has(r.kollekciya))
    if (incompleteOnly) res = res.filter((r) => r.completeness < 0.5)
    return search.trim() ? res.filter((r) => modelMatches(r, search.trim().toLowerCase())) : res
  }, [rows, selectedStatusIds, selectedCategoryIds, selectedCollectionNames, incompleteOnly, search])
  // Group filtered rows
  const grouped = useMemo(() => {
    if (groupBy === "none") return [{ key: "_all", label: "", items: filtered }]
    const map = new Map<string, MatrixRow[]>()
    for (const r of filtered) {
      const k = getGroupKey(r, groupBy, statusNameById)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(r)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b, "ru")).map(([key, items]) => ({ key, label: key, items }))
  }, [filtered, groupBy, statusNameById])
  const toggleExpand = useCallback((id: number) => setExpandedRows((prev) => toggleSet(prev, id)), [])
  const toggleSelect = useCallback((kod: string) => setSelectedKods((prev) => toggleSet(prev, kod)), [])
  const toggleSelectAllVisible = useCallback(() => {
    setSelectedKods((prev) => {
      const visibleKods = filtered.map((r) => r.kod)
      const next = new Set(prev)
      const allSelected = visibleKods.length > 0 && visibleKods.every((k) => prev.has(k))
      for (const k of visibleKods) allSelected ? next.delete(k) : next.add(k)
      return next
    })
  }, [filtered])
  // Bulk actions
  const handleBulkSetStatus = useCallback(async (statusId: number) => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    try {
      await bulkUpdateModelStatus(kods, statusId)
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      setSelectedKods(new Set()); setBulkStatusOpen(false)
    } catch (err) { window.alert(`Не удалось обновить статус: ${(err as Error).message}`) }
  }, [selectedKods, queryClient])
  const handleBulkDuplicate = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    for (const srcKod of kods) {
      const newKod = window.prompt(`Дублировать «${srcKod}»: введите новый kod`, `${srcKod}_copy`)
      if (!newKod) continue
      try { await duplicateModel(srcKod, newKod.trim()) } catch (err) { window.alert(`Не удалось дублировать ${srcKod}: ${(err as Error).message}`) }
    }
    await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    setSelectedKods(new Set())
  }, [selectedKods, queryClient])
  const handleBulkArchive = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0 || !window.confirm(`Архивировать ${kods.length} модель(и) и все связанные вариации/артикулы/SKU?`)) return
    for (const kod of kods) {
      try { await archiveModel(kod) } catch (err) { window.alert(`Не удалось архивировать ${kod}: ${(err as Error).message}`) }
    }
    await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    setSelectedKods(new Set())
  }, [selectedKods, queryClient])
  // Single-row actions
  const handleRowDuplicate = useCallback(async (srcKod: string) => {
    const newKod = window.prompt(`Дублировать «${srcKod}»: введите новый kod`, `${srcKod}_copy`)
    if (!newKod) return
    try {
      await duplicateModel(srcKod, newKod.trim())
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    } catch (err) { window.alert(`Не удалось дублировать: ${(err as Error).message}`) }
  }, [queryClient])
  const handleRowArchive = useCallback(async (kod: string) => {
    if (!window.confirm(`Архивировать «${kod}» и все связанные вариации/артикулы/SKU?`)) return
    try {
      await archiveModel(kod)
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    } catch (err) { window.alert(`Не удалось архивировать: ${(err as Error).message}`) }
  }, [queryClient])
  const allVisibleSelected = filtered.length > 0 && filtered.every((r) => selectedKods.has(r.kod))
  return (
    <>
      <div className="px-6 py-4 max-w-[1600px] mx-auto">
        {/* Filter bar */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <SearchBox value={search} onChange={setSearch} placeholder="Код, название, артикул вариации…" />
          <button onClick={() => setIncompleteOnly(!incompleteOnly)} className={`px-2.5 py-1 text-xs rounded-md flex items-center gap-1.5 transition-colors ${incompleteOnly ? "bg-amber-100 text-amber-800" : "text-stone-600 hover:bg-stone-100"}`}>
            <AlertCircle className="w-3 h-3" /> Незаполненные
          </button>
          <div className="ml-auto flex items-center gap-2">
            <label className="text-[11px] uppercase tracking-wider text-stone-500">Группировка:</label>
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)} className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none">
              {GROUP_BY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <span className="text-xs text-stone-500 tabular-nums">{filtered.length} из {rows.length}</span>
          </div>
        </div>
        {/* Category chips */}
        <FilterChips title="Категории:" items={kategorii.map((k) => ({ key: String(k.id), value: k.id, label: k.nazvanie }))} selected={selectedCategoryIds} onChange={setSelectedCategoryIds} />
        {/* Collection chips */}
        <FilterChips title="Коллекции:" items={kollekcii.map((k) => ({ key: String(k.id), value: k.nazvanie, label: k.nazvanie }))} selected={selectedCollectionNames} onChange={setSelectedCollectionNames} />
        {/* Status chips with counts */}
        <FilterChips title="Статусы:" items={modelStatuses.map((s) => ({ key: String(s.id), value: s.id, label: s.nazvanie, count: statusCounts.get(s.id) ?? 0 }))} selected={selectedStatusIds} onChange={setSelectedStatusIds} className="mb-3" />
        {/* Table */}
        <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50/80 border-b border-stone-200">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="w-8 px-2 py-2.5" />
                <th className="w-10 px-3 py-2.5"><input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAllVisible} style={{ accentColor: "#1C1917" }} className="rounded border-stone-300" aria-label="Выбрать все" /></th>
                {MODEL_COLUMNS.map(([label, cls]) => <th key={label} className={`px-3 py-2.5 font-medium ${cls ?? ""}`}>{label}</th>)}
                <th className="w-10 px-2 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {grouped.map((group) => (
                <Fragment key={`group-${group.key}`}>
                  {groupBy !== "none" && (
                    <tr className="bg-stone-100/60 border-b border-stone-200">
                      <td colSpan={13} className="px-3 py-2"><div className="flex items-center gap-2"><span className="text-sm font-medium text-stone-800">{group.label}</span><span className="text-xs text-stone-500 tabular-nums">· {group.items.length}</span></div></td>
                    </tr>
                  )}
                  {group.items.map((m) => {
                    const canExpand = m.modeli.length >= 2
                    const isExpanded = expandedRows.has(m.id)
                    const checked = selectedKods.has(m.kod)
                    const variantSizes = new Set<string>()
                    // Razmery: derive from variant rossiyskiy_razmer values that match the standard ladder.
                    for (const v of m.modeli) {
                      const ru = (v.rossiyskiy_razmer ?? "").toUpperCase().trim()
                      if ((RAZMER_LADDER as readonly string[]).includes(ru)) variantSizes.add(ru)
                    }
                    return (
                      <Fragment key={`${m.kod}-row`}>
                        <tr className="border-b border-stone-100 hover:bg-stone-50/60 group">
                          <td className="px-2 py-3">
                            {canExpand ? (
                              <button onClick={() => toggleExpand(m.id)} className="p-0.5 hover:bg-stone-200 rounded" aria-label={isExpanded ? "Свернуть вариации" : "Развернуть вариации"}>
                                {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-stone-500" /> : <ChevronRight className="w-3.5 h-3.5 text-stone-500" />}
                              </button>
                            ) : (
                              <Tooltip text={m.modeli.length === 1 ? "У модели одна вариация — раскрытие не требуется" : "Нет вариаций"}><span className="text-stone-300 text-xs">·</span></Tooltip>
                            )}
                          </td>
                          <td className="px-3 py-3"><input type="checkbox" checked={checked} onChange={() => toggleSelect(m.kod)} onClick={(e) => e.stopPropagation()} style={{ accentColor: "#1C1917" }} className="rounded border-stone-300" aria-label={`Выбрать ${m.kod}`} /></td>
                          <td className="px-3 py-3 cursor-pointer" onClick={() => onOpen(m.kod)}>
                            <div className="font-medium text-stone-900 hover:underline font-mono">{m.kod}</div>
                            <div className="text-xs text-stone-500 truncate max-w-[220px]">{m.nazvanie_sayt || <span className="italic text-stone-400">без названия</span>}</div>
                          </td>
                          <td className="px-3 py-3 text-stone-700">{m.kategoriya ?? "—"}</td>
                          <td className="px-3 py-3"><div className="text-stone-700">{m.kollekciya ?? "—"}</div><div className="text-[11px] text-stone-400">{m.tip_kollekcii ?? ""}</div></td>
                          <td className="px-3 py-3 text-stone-700">{m.fabrika ?? "—"}</td>
                          <td className="px-3 py-3"><StatusBadge statusId={m.status_id ?? 0} /></td>
                          <td className="px-3 py-3"><div className="flex items-center gap-0.5">{RAZMER_LADDER.map((sz) => <span key={sz} className={`text-[10px] px-1 py-0.5 rounded ${variantSizes.has(sz) ? "bg-stone-900 text-white" : "bg-stone-50 text-stone-300 ring-1 ring-inset ring-stone-200"}`}>{sz}</span>)}</div></td>
                          <td className="px-3 py-3"><ColorChips modelKod={m.kod} count={m.cveta_cnt} /></td>
                          <td className="px-3 py-3"><CompletenessRing value={m.completeness} size={16} hideLabel /></td>
                          <td className="px-3 py-3 text-right tabular-nums text-stone-600"><span className="text-stone-900 font-medium">{m.cveta_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{m.artikuly_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{m.tovary_cnt}</span></td>
                          <td className="px-3 py-3 text-stone-500 text-xs">{relativeDate(m.updated_at)}</td>
                          <td className="px-2 py-3 relative">
                            <button className="p-1 hover:bg-stone-100 rounded opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => { e.stopPropagation(); setOpenMenuKod((cur) => (cur === m.kod ? null : m.kod)) }} aria-label="Действия">
                              <MoreHorizontal className="w-3.5 h-3.5 text-stone-500" />
                            </button>
                            {openMenuKod === m.kod && (
                              <div className="absolute right-2 top-9 z-20 w-40 bg-white border border-stone-200 rounded-md shadow-lg py-1" onClick={(e) => e.stopPropagation()}>
                                <button onClick={() => { setOpenMenuKod(null); onOpen(m.kod) }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"><Edit3 className="w-3 h-3" /> Редактировать</button>
                                <button onClick={() => { setOpenMenuKod(null); handleRowDuplicate(m.kod) }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"><Copy className="w-3 h-3" /> Дублировать</button>
                                <button onClick={() => { setOpenMenuKod(null); handleRowArchive(m.kod) }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 text-red-600 flex items-center gap-2"><Archive className="w-3 h-3" /> Архивировать</button>
                              </div>
                            )}
                          </td>
                        </tr>
                        {isExpanded && m.modeli.map((v) => (
                          <tr key={`v-${v.id}`} className="bg-stone-50/40 border-b border-stone-100 text-xs">
                            <td colSpan={2} />
                            <td className="pl-3 py-2 pr-3"><div className="flex items-center gap-2"><div className="w-4 h-px bg-stone-300" /><span className="font-medium text-stone-800 font-mono">{v.kod}</span></div><div className="text-[11px] text-stone-500 ml-6 mt-0.5 truncate max-w-[200px]">{v.nazvanie}</div></td>
                            <td className="px-3 py-2 text-stone-400">—</td>
                            <td className="px-3 py-2"><div className="flex items-center gap-1 text-stone-500"><Building2 className="w-3 h-3 text-stone-400" />{v.importer_short ?? "—"}</div></td>
                            <td className="px-3 py-2 font-mono text-[11px] text-stone-500">{v.artikul_modeli ?? "—"}</td>
                            <td className="px-3 py-2"><StatusBadge statusId={v.status_id ?? 0} compact /></td>
                            <td className="px-3 py-2 text-stone-400 text-[10px]">RU: {v.rossiyskiy_razmer ?? "—"}</td>
                            <td />
                            <td />
                            <td className="px-3 py-2 text-right tabular-nums text-stone-600"><span className="text-stone-300">—</span><span className="text-stone-300 mx-1">/</span><span className="text-stone-700 font-medium">{v.artikuly_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{v.tovary_cnt}</span></td>
                            <td className="px-3 py-2 text-stone-400">—</td>
                            <td />
                          </tr>
                        ))}
                      </Fragment>
                    )
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-stone-500 flex items-center gap-2"><Info className="w-3.5 h-3.5 shrink-0" /><span>Стрелка ▶ раскрывает вариации. Клик по коду — карточка модели.</span></div>
      </div>
      {selectedKods.size > 0 && (
        <BulkBar
          selectedCount={selectedKods.size}
          modelStatuses={modelStatuses}
          bulkStatusOpen={bulkStatusOpen}
          onToggleBulkStatus={() => setBulkStatusOpen((v) => !v)}
          onPickStatus={handleBulkSetStatus}
          onDuplicate={handleBulkDuplicate}
          onExport={() => window.alert(`Экспорт CSV для ${selectedKods.size} моделей — TODO Wave 3+`)}
          onArchive={handleBulkArchive}
          onClear={() => { setSelectedKods(new Set()); setBulkStatusOpen(false) }}
        />
      )}
    </>
  )
}
/**
 * BulkBar — обёртка над atomic BulkActionsBar с дополнительной выпадашкой
 * статусов. atomic BulkActionsBar не поддерживает submenu из коробки, поэтому
 * рисуем контейнер сами и переиспользуем стилистику.
 */
function BulkBar({ selectedCount, modelStatuses, bulkStatusOpen, onToggleBulkStatus, onPickStatus, onDuplicate, onExport, onArchive, onClear }: { selectedCount: number; modelStatuses: StatusOption[]; bulkStatusOpen: boolean; onToggleBulkStatus: () => void; onPickStatus: (id: number) => void; onDuplicate: () => void; onExport: () => void; onArchive: () => void; onClear: () => void }) {
  return (
    <div className="catalog-scope fixed bottom-0 left-0 right-0 z-40 border-t border-stone-200 bg-white px-6 py-3 flex items-center gap-3 shrink-0 shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.08)]" onClick={(e) => e.stopPropagation()}>
      <span className="text-sm">Выбрано: <span className="font-medium tabular-nums">{selectedCount}</span></span>
      <div className="h-5 w-px bg-stone-200" />
      <div className="relative">
        <button type="button" onClick={onToggleBulkStatus} className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5">Изменить статус<ChevronDown className="w-3 h-3" /></button>
        {bulkStatusOpen && (
          <div className="absolute bottom-9 left-0 z-50 w-48 bg-white border border-stone-200 rounded-md shadow-lg py-1">
            {modelStatuses.map((s) => (
              <button key={s.id} type="button" onClick={() => onPickStatus(s.id)} className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2">
                <StatusBadge status={{ nazvanie: s.nazvanie, color: s.color }} compact size="sm" />
              </button>
            ))}
          </div>
        )}
      </div>
      <button type="button" onClick={onDuplicate} className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"><Copy className="w-3 h-3" /> Дублировать</button>
      <button type="button" onClick={onExport} className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"><Download className="w-3 h-3" /> Экспорт выбранного</button>
      <button type="button" onClick={onArchive} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md flex items-center gap-1.5"><Archive className="w-3 h-3" /> Архивировать</button>
      <button type="button" onClick={onClear} className="ml-auto px-3 py-1 text-xs text-stone-500 hover:bg-stone-100 rounded-md">Очистить</button>
    </div>
  )
}
/**
 * ColorChips — placeholder swatches для матрицы. MatrixRow не несёт реальные
 * color codes (только cveta_cnt) — рендерим N стилизованных кружочков из
 * deterministic hash-based swatchColor(modelKod#i). При раскрытии в карточке
 * пользователь увидит реальные цвета.
 */
function ColorChips({ modelKod, count }: { modelKod: string; count: number }) {
  if (count === 0) return <span className="text-stone-300 text-xs">—</span>
  const visible = Math.min(count, 6)
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: visible }).map((_, i) => <span key={i} className="rounded-full ring-1 ring-stone-200" style={{ width: 12, height: 12, background: swatchColor(`${modelKod}#${i}`) }} />)}
      {count > 6 && <span className="text-[10px] text-stone-400 ml-1 tabular-nums">+{count - 6}</span>}
    </div>
  )
}
// ─── Artikuly registry tab ─────────────────────────────────────────────────
function ArtikulyTable() {
  const { data, isLoading } = useQuery({ queryKey: ["artikuly-registry"], queryFn: fetchArtikulyRegistry, staleTime: 5 * 60 * 1000 })
  const [search, setSearch] = useState("")
  const filtered = useMemo(() => {
    if (!data) return []
    const q = search.trim().toLowerCase()
    return q ? data.filter((a) => a.artikul.toLowerCase().includes(q) || (a.model_osnova_kod ?? "").toLowerCase().includes(q) || (a.cvet_color_code ?? "").toLowerCase().includes(q)) : data
  }, [data, search])
  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      <RegistryTop search={search} setSearch={setSearch} placeholder="Артикул, модель, цвет…" count={filtered.length} total={data?.length ?? 0} />
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <RegistryHead labels={["Артикул", "Модель", "Вариация", "Цвет", "Статус", "WB номенкл.", "OZON", "SKU"]} rightLabel="SKU" />
          <tbody>
            {filtered.slice(0, 100).map((a) => (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-900">{a.artikul}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{a.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{a.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5"><div className="flex items-center gap-1.5"><ColorSwatch colorCode={a.cvet_color_code} size={14} /><span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span><span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span></div></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={a.status_id ?? 0} compact /></td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500 tabular-nums">{a.nomenklatura_wb ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500">{a.artikul_ozon ?? "—"}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-stone-700">{a.tovary_cnt}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 100 && <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">Показаны первые 100 из {filtered.length}.</div>}
      </div>
    </div>
  )
}
// ─── Tovary registry tab ───────────────────────────────────────────────────
const CHANNELS = [
  { id: "all", label: "Все" }, { id: "wb", label: "WB" }, { id: "ozon", label: "Ozon" }, { id: "sayt", label: "Сайт" }, { id: "lamoda", label: "Lamoda" },
] as const
function TovaryTable() {
  const { data, isLoading } = useQuery({ queryKey: ["tovary-registry"], queryFn: fetchTovaryRegistry, staleTime: 5 * 60 * 1000 })
  const [search, setSearch] = useState("")
  const [channelFilter, setChannelFilter] = useState<(typeof CHANNELS)[number]["id"]>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
  const [visibleCount, setVisibleCount] = useState(100)
  const productStatuses = CATALOG_STATUSES.filter((s) => s.tip === "product")
  const resetVisible = () => setVisibleCount(100)
  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (channelFilter === "wb") res = res.filter((t) => t.status_id !== null)
    else if (channelFilter === "ozon") res = res.filter((t) => t.status_ozon_id !== null)
    else if (channelFilter === "sayt") res = res.filter((t) => t.status_sayt_id !== null)
    else if (channelFilter === "lamoda") res = res.filter((t) => t.status_lamoda_id !== null)
    if (statusFilter !== "all") res = res.filter((t) => t.status_id === statusFilter || t.status_ozon_id === statusFilter || t.status_sayt_id === statusFilter || t.status_lamoda_id === statusFilter)
    const q = search.trim().toLowerCase()
    return q ? res.filter((t) => t.barkod.includes(q) || (t.model_osnova_kod ?? "").toLowerCase().includes(q) || (t.artikul ?? "").toLowerCase().includes(q)) : res
  }, [data, channelFilter, statusFilter, search])
  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      {/* Channel tabs */}
      <div className="flex items-center gap-1 mb-3">
        {CHANNELS.map((c) => <button key={c.id} onClick={() => { setChannelFilter(c.id); resetVisible() }} className={`px-3 py-1.5 text-xs rounded-md transition-colors ${channelFilter === c.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}>{c.label}</button>)}
        <div className="h-4 w-px bg-stone-200 mx-1" />
        <select value={statusFilter === "all" ? "all" : String(statusFilter)} onChange={(e) => { setStatusFilter(e.target.value === "all" ? "all" : Number(e.target.value)); resetVisible() }} className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none">
          <option value="all">Все статусы</option>
          {productStatuses.map((s) => <option key={s.id} value={s.id}>{s.nazvanie}</option>)}
        </select>
      </div>
      {/* Search + count */}
      <RegistryTop search={search} setSearch={(v) => { setSearch(v); resetVisible() }} placeholder="Баркод, модель, артикул…" count={filtered.length} total={data?.length ?? 0} />
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <RegistryHead labels={["Баркод", "Модель", "Вариация", "Цвет", "Размер", "WB", "OZON", "Сайт", "Lamoda"]} borderedLabel="WB" />
          <tbody>
            {filtered.slice(0, visibleCount).map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-700">{t.barkod}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{t.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{t.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5"><div className="flex items-center gap-1.5"><ColorSwatch colorCode={t.cvet_color_code} size={14} /><span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span></div></td>
                <td className="px-3 py-2.5 font-mono text-xs">{t.razmer ?? "—"}</td>
                <td className="px-3 py-2.5 border-l border-stone-100"><StatusBadge statusId={t.status_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_ozon_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_sayt_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_lamoda_id ?? 0} compact /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > visibleCount && (
          <div className="px-3 py-3 border-t border-stone-100 flex items-center justify-between">
            <span className="text-xs text-stone-400">Показано {visibleCount} из {filtered.length}</span>
            <button onClick={() => setVisibleCount((v) => v + 100)} className="text-xs text-stone-700 hover:text-stone-900 px-3 py-1 hover:bg-stone-100 rounded-md transition-colors">Показать ещё 100</button>
          </div>
        )}
      </div>
    </div>
  )
}
function RegistryTop({ search, setSearch, placeholder, count, total }: { search: string; setSearch: (v: string) => void; placeholder: string; count: number; total: number }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <SearchBox value={search} onChange={setSearch} placeholder={placeholder} />
      <div className="ml-auto text-xs text-stone-500 tabular-nums">{count} из {total}</div>
    </div>
  )
}
function RegistryHead({ labels, rightLabel, borderedLabel }: { labels: string[]; rightLabel?: string; borderedLabel?: string }) {
  return (
    <thead className="bg-stone-50/80 border-b border-stone-200">
      <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
        {labels.map((label) => (
          <th key={label} className={`px-3 py-2.5 font-medium ${label === rightLabel ? "text-right" : ""} ${label === borderedLabel ? "border-l border-stone-200" : ""}`}>{label}</th>
        ))}
      </tr>
    </thead>
  )
}
// ─── Main MatrixPage ───────────────────────────────────────────────────────
export function MatrixPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [listTab, setListTab] = useState<ListTab>("modeli_osnova")
  const queryClient = useQueryClient()
  const matrixQ = useQuery({ queryKey: ["matrix-list"], queryFn: fetchMatrixList, staleTime: 3 * 60 * 1000 })
  const kategoriiQ = useQuery({ queryKey: ["kategorii"], queryFn: fetchKategorii, staleTime: 10 * 60 * 1000 })
  const kollekciiQ = useQuery({ queryKey: ["kollekcii"], queryFn: fetchKollekcii, staleTime: 10 * 60 * 1000 })
  const statusyQ = useQuery({ queryKey: ["statusy"], queryFn: fetchStatusy, staleTime: 30 * 60 * 1000 })
  const openModel = useCallback((kod: string) => {
    const next = new URLSearchParams(searchParams)
    next.set("model", kod)
    next.delete("id")
    setSearchParams(next)
  }, [searchParams, setSearchParams])
  const handleNewModel = useCallback(async () => {
    const kod = window.prompt("Код новой модели (latin, без пробелов):", "")
    if (!kod || !kod.trim()) return
    try {
      const created = await createModel({ kod: kod.trim() })
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      const next = new URLSearchParams(searchParams)
      next.set("model", created)
      next.delete("id")
      setSearchParams(next)
    } catch (err) { window.alert(`Не удалось создать модель: ${(err as Error).message}`) }
  }, [queryClient, searchParams, setSearchParams])
  // ?model=KOD opens B3's <ModelCardModal /> as overlay from CatalogLayout.
  const rows = matrixQ.data ?? []
  const kategorii = kategoriiQ.data ?? []
  const kollekcii = kollekciiQ.data ?? []
  const modelStatuses = (statusyQ.data ?? []).filter((s) => s.tip === "model")
  const totalVariations = rows.reduce((s, r) => s + r.modeli_cnt, 0)
  const totalArts = rows.reduce((s, r) => s + r.artikuly_cnt, 0)
  const totalSku = rows.reduce((s, r) => s + r.tovary_cnt, 0)
  const listTabs = [
    { id: "modeli_osnova", label: "Базовые модели", count: rows.length },
    { id: "artikuly", label: "Артикулы (реестр)", count: totalArts },
    { id: "tovary", label: "SKU (реестр)", count: totalSku },
  ] as const
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="max-w-[1600px] mx-auto flex items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1 className="text-3xl text-stone-900 cat-font-serif">Матрица товаров</h1>
            <div className="text-sm text-stone-500 mt-1">{rows.length} моделей · {totalVariations} вариаций · {totalArts} артикулов · {totalSku} SKU</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => window.alert("Экспорт CSV — TODO Wave 3+")} className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 border border-stone-200"><Download className="w-3.5 h-3.5" /> Экспорт</button>
            <button onClick={handleNewModel} className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> Новая модель</button>
          </div>
        </div>
      </div>
      {/* Tabs */}
      <div className="border-b border-stone-200 px-6 shrink-0">
        <div className="max-w-[1600px] mx-auto flex gap-1">
          {listTabs.map((t) => (
            <button key={t.id} onClick={() => setListTab(t.id)} className={`relative px-3 py-2.5 text-sm transition-colors ${listTab === t.id ? "text-stone-900 font-medium" : "text-stone-500 hover:text-stone-800"}`}>
              {t.label}<span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              {listTab === t.id && <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />}
            </button>
          ))}
        </div>
      </div>
      {/* Content */}
      <div className="flex-1 overflow-auto pb-20">
        {matrixQ.isLoading && listTab === "modeli_osnova" && <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>}
        {matrixQ.error && <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки: {String(matrixQ.error)}</div>}
        {listTab === "modeli_osnova" && !matrixQ.isLoading && !matrixQ.error && (
          <ModeliOsnovaTable rows={rows} kategorii={kategorii} kollekcii={kollekcii} modelStatuses={modelStatuses} onOpen={openModel} />
        )}
        {listTab === "artikuly" && <ArtikulyTable />}
        {listTab === "tovary" && <TovaryTable />}
      </div>
    </div>
  )
}
