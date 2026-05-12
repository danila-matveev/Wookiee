import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Archive, Building2, ChevronDown, ChevronRight, Copy, Download, Edit3, Info, MoreHorizontal, Plus, Search } from "lucide-react"
import { archiveModel, bulkUpdateModelStatus, duplicateModel, fetchArtikulyRegistry, fetchBrendy, fetchKategorii, fetchKollekcii, fetchMatrixList, fetchStatusy, fetchTovaryRegistry, getUiPref, setUiPref } from "@/lib/catalog/service"
import type { ArtikulRow, Brend, MatrixRow, TovarRow } from "@/lib/catalog/service"
import { StatusBadge, CATALOG_STATUSES } from "@/components/catalog/ui/status-badge"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { Tooltip } from "@/components/catalog/ui/tooltip"
import { CellText } from "@/components/catalog/ui/cell-text"
import { NewModelModal } from "@/components/catalog/ui/new-model-modal"
import { SortableHeader } from "@/components/catalog/ui/sortable-header"
import { Pagination } from "@/components/catalog/ui/pagination"
import { FilterBar } from "@/components/catalog/ui/filter-bar"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { useResizableColumns, type ResizerBindings } from "@/hooks/use-resizable-columns"
import { useTableSort, type SortState } from "@/hooks/use-table-sort"
import { usePagination } from "@/hooks/use-pagination"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useCollapsibleGroups } from "@/hooks/use-collapsible-groups"
import { useColumnConfig } from "@/hooks/use-column-config"
import { MATRIX_COLUMNS } from "@/lib/catalog/column-catalogs"
import { ColumnsManager } from "@/components/catalog/ui/columns-manager"
import { downloadCsv } from "@/lib/catalog/csv-export"
import { translateError } from "@/lib/catalog/error-translator"
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
// W9.4 — старый компонент `FilterChips` (всегда открытые ряды чипов по одному
// измерению) заменён компактным `FilterBar` (см. import выше). Сохраняем только
// `toggleSet` и тривиальные типы, которые могут пригодиться в других местах.
// ─── Matrix list view (Базовые модели) — Wave 2 B1 ─────────────────────────
type GroupBy = "none" | "brand" | "kategoriya" | "kollekciya" | "fabrika" | "status"
type ListTab = "modeli_osnova" | "artikuly" | "tovary"
type StatusOption = { id: number; nazvanie: string; tip: string; color: string | null }
const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "none", label: "Без группировки" },
  { value: "brand", label: "По бренду" },
  { value: "kategoriya", label: "По категории" },
  { value: "kollekciya", label: "По коллекции" },
  { value: "fabrika", label: "По фабрике" },
  { value: "status", label: "По статусу" },
]
// W3.2 — добавлена колонка «Бренд» между «Название» и «Категория».
// W8.1 — третий слот = sort key (или null, если колонку не сортируем).
type ModeliOsnovaSortKey =
  | "nazvanie" | "brand" | "kategoriya" | "kollekciya" | "fabrika"
  | "status" | "completeness" | "cv_art_sku" | "obnovleno"
const MODEL_COLUMNS: readonly (readonly [string, string?, ModeliOsnovaSortKey?])[] = [
  ["Название", undefined, "nazvanie"],
  ["Бренд", undefined, "brand"],
  ["Категория", undefined, "kategoriya"],
  ["Коллекция", undefined, "kollekciya"],
  ["Фабрика", undefined, "fabrika"],
  ["Статус", undefined, "status"],
  ["Размеры"],
  ["Цвета"],
  ["Заполн.", undefined, "completeness"],
  ["Цв / Арт / SKU", "text-right", "cv_art_sku"],
  ["Обновлено", undefined, "obnovleno"],
] as const
// W7.3 — Колонки для CSV-экспорта матрицы.  Метки берём из MODEL_COLUMNS,
// плюс две вспомогательные (kod / artikul_modeli) для машинной идентификации.
const MATRIX_EXPORT_COLUMNS: { key: string; label: string }[] = [
  { key: "kod", label: "Код" },
  { key: "nazvanie_sayt", label: "Название" },
  { key: "brand", label: "Бренд" },
  { key: "kategoriya", label: "Категория" },
  { key: "kollekciya", label: "Коллекция" },
  { key: "fabrika", label: "Фабрика" },
  { key: "status", label: "Статус" },
  { key: "cveta_cnt", label: "Цветов" },
  { key: "artikuly_cnt", label: "Артикулов" },
  { key: "tovary_cnt", label: "SKU" },
  { key: "completeness", label: "Заполненность" },
  { key: "updated_at", label: "Обновлено" },
]
function matrixRowToExport(r: MatrixRow, statusNameById: Map<number, string>): Record<string, unknown> {
  return {
    kod: r.kod,
    nazvanie_sayt: r.nazvanie_sayt ?? "",
    brand: r.brand ?? "",
    kategoriya: r.kategoriya ?? "",
    kollekciya: r.kollekciya ?? "",
    fabrika: r.fabrika ?? "",
    status: r.status_id != null ? (statusNameById.get(r.status_id) ?? `#${r.status_id}`) : "",
    cveta_cnt: r.cveta_cnt,
    artikuly_cnt: r.artikuly_cnt,
    tovary_cnt: r.tovary_cnt,
    completeness: r.completeness,
    updated_at: r.updated_at ?? "",
  }
}
// Column IDs + default widths for useResizableColumns (W1.5). Order must match MODEL_COLUMNS.
const MODEL_COLUMN_IDS = [
  { id: "nazvanie", defaultWidth: 240 },
  { id: "brand", defaultWidth: 110 },
  { id: "kategoriya", defaultWidth: 140 },
  { id: "kollekciya", defaultWidth: 160 },
  { id: "fabrika", defaultWidth: 140 },
  { id: "status", defaultWidth: 140 },
  { id: "razmery", defaultWidth: 170 },
  { id: "cveta", defaultWidth: 170 },
  { id: "zapoln", defaultWidth: 80 },
  { id: "cv_art_sku", defaultWidth: 130 },
  { id: "obnovleno", defaultWidth: 110 },
] as const
function getGroupKey(row: MatrixRow, groupBy: GroupBy, statusNameById: Map<number, string>): string {
  switch (groupBy) {
    case "brand": return row.brand ?? "Без бренда"
    case "kategoriya": return row.kategoriya ?? "Без категории"
    case "kollekciya": return row.kollekciya ?? "Без коллекции"
    case "fabrika": return row.fabrika ?? "Без фабрики"
    case "status": return row.status_id != null ? (statusNameById.get(row.status_id) ?? `Статус #${row.status_id}`) : "Без статуса"
    default: return ""
  }
}
// W9.3 — расширенный поиск: бренд, категория, коллекция, фабрика,
// nazvanie_etiketka, плюс все артикулы вариаций. Регистр-инвариантно.
function modelMatches(row: MatrixRow, query: string) {
  const q = query.toLowerCase()
  if (!q) return true
  const headerFields = [
    row.kod,
    row.nazvanie_sayt,
    row.nazvanie_etiketka,
    row.brand,
    row.kategoriya,
    row.kollekciya,
    row.fabrika,
  ]
  for (const f of headerFields) {
    if (f && f.toLowerCase().includes(q)) return true
  }
  return row.modeli.some((v) =>
    (v.kod ?? "").toLowerCase().includes(q) ||
    (v.nazvanie ?? "").toLowerCase().includes(q) ||
    (v.artikul_modeli ?? "").toLowerCase().includes(q)
  )
}
// W8.3 — собирает текст tooltip-а для CompletenessRing.
// Показывает топ-5 незаполненных полей с их «весом» (pp от общего completeness)
// + счётчик «и ещё N», если полей больше пяти.
function buildCompletenessTooltip(row: MatrixRow): string {
  const pct = Math.round(row.completeness * 100)
  if (row.missing_fields.length === 0) return `Заполнено полностью (${pct}%)`
  const top = row.missing_fields.slice(0, 5)
  const tail = row.missing_fields.length - top.length
  const lines = top.map((f) => `${f.label} (${f.weight}%)`).join(" · ")
  const moreSuffix = tail > 0 ? ` · и ещё ${tail}` : ""
  return `Заполненность ${pct}%. Не заполнено: ${lines}${moreSuffix}`
}
function ModeliOsnovaTable({ rows, brendy, kategorii, kollekcii, modelStatuses, onOpen, onRegisterExport }: { rows: MatrixRow[]; brendy: Brend[]; kategorii: { id: number; nazvanie: string }[]; kollekcii: { id: number; nazvanie: string }[]; modelStatuses: StatusOption[]; onOpen: (kod: string) => void; onRegisterExport?: (fn: (() => void) | null) => void }) {
  const queryClient = useQueryClient()
  const { widths: colWidths, bindResizer } = useResizableColumns("matrix.modeli", [...MODEL_COLUMN_IDS])
  // W9.5 — конфигуратор колонок матрицы. Видимость управляет рендер-ключами
  // MODEL_COLUMN_IDS; для полей из БД, не имеющих рендерера, тоггл активирует
  // их в каталоге, но в таблице они пока не отрисовываются (TODO ниже).
  const columnConfig = useColumnConfig("matrix", MATRIX_COLUMNS)
  const isColVisible = (key: string): boolean => columnConfig.visibility[key] !== false
  // Маппинг render-ключей (MODEL_COLUMN_IDS) → ключи каталога колонок.
  // Совпадают по именам, кроме razmery / cveta / zapoln / cv_art_sku / obnovleno.
  const renderKeyToCatalogKey: Record<string, string> = {
    nazvanie: "nazvanie",
    brand: "brand",
    kategoriya: "kategoriya",
    kollekciya: "kollekciya",
    fabrika: "fabrika",
    status: "status",
    razmery: "razmery",
    cveta: "cveta",
    zapoln: "completeness",
    cv_art_sku: "cv_art_sku",
    obnovleno: "obnovleno",
  }
  const isRenderColVisible = (renderKey: string): boolean => {
    const catalogKey = renderKeyToCatalogKey[renderKey] ?? renderKey
    return isColVisible(catalogKey)
  }
  const [search, setSearch] = useState("")
  // W9.3 — дебаунс 300мс. Фильтрация по тысячам моделей на каждом keystroke
  // даёт заметные подвисания на больших каталогах; debounced value читается
  // в `filtered`/`useMemo`-деп.
  const debouncedSearch = useDebouncedValue(search, 300)
  // W3.2 — brand chip filter.
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<number>>(new Set())
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<number>>(new Set())
  const [selectedCollectionNames, setSelectedCollectionNames] = useState<Set<string>>(new Set())
  const [selectedStatusIds, setSelectedStatusIds] = useState<Set<number>>(new Set())
  const [incompleteOnly, setIncompleteOnly] = useState(false)
  const [groupBy, setGroupBy] = useState<GroupBy>("none")
  // W9.6 — Notion-style collapsible group headers.
  const { isCollapsed: isGroupCollapsed, toggle: toggleGroupCollapsed } = useCollapsibleGroups("matrix-modeli")
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [selectedKods, setSelectedKods] = useState<Set<string>>(new Set())
  const [openMenuKod, setOpenMenuKod] = useState<string | null>(null)
  const [bulkStatusOpen, setBulkStatusOpen] = useState(false)
  const groupByLoadedRef = useRef(false)
  // W8.1 — sort state + persist via ui_preferences.
  const { sort, toggleSort, setSortState, sortRows } = useTableSort<ModeliOsnovaSortKey>()
  const sortLoadedRef = useRef(false)
  // W8.2 — pagination state.
  const { page, setPage, pageSize, setPageSize, paginate, resetPage } = usePagination(50)
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
  // W8.1 — hydrate sort from ui_preferences (key: "sort:matrix:modeli").
  useEffect(() => {
    if (sortLoadedRef.current) return
    sortLoadedRef.current = true
    getUiPref<SortState<ModeliOsnovaSortKey>>("matrix.modeli", "sort").then((v) => {
      if (v && v.column != null && v.direction != null) setSortState(v)
    }).catch(() => { /* ignore */ })
  }, [setSortState])
  // Persist sort changes after initial hydration.
  useEffect(() => {
    if (!sortLoadedRef.current) return
    setUiPref("matrix.modeli", "sort", sort).catch(() => { /* non-fatal */ })
  }, [sort])
  // Close more-menu / bulk-status dropdown when clicking elsewhere
  useEffect(() => {
    if (!openMenuKod && !bulkStatusOpen) return
    const onDocClick = () => { setOpenMenuKod(null); setBulkStatusOpen(false) }
    document.addEventListener("click", onDocClick)
    return () => document.removeEventListener("click", onDocClick)
  }, [openMenuKod, bulkStatusOpen])
  const statusNameById = useMemo(() => new Map(modelStatuses.map((s) => [s.id, s.nazvanie])), [modelStatuses])
  // Live status lookup by id — used to render <StatusBadge> for both parent
  // modeli_osnova rows (status_ids 20–26) and variation modeli rows. The
  // hardcoded CATALOG_STATUSES legacy table only has ids 1–7 (stale fixture),
  // so we cannot rely on statusId-based lookup inside StatusBadge here.
  const statusById = useMemo(() => new Map(modelStatuses.map((s) => [s.id, s])), [modelStatuses])
  // Status counts (from full rows, not filtered) for chip badges
  const statusCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const r of rows) if (r.status_id != null) acc.set(r.status_id, (acc.get(r.status_id) ?? 0) + 1)
    return acc
  }, [rows])
  // W3.2 — brand counts (from full rows, not filtered) for chip badges.
  const brandCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const r of rows) if (r.brand_id != null) acc.set(r.brand_id, (acc.get(r.brand_id) ?? 0) + 1)
    return acc
  }, [rows])
  // W9.4 — category / collection / season counts (used for chip badges).
  const categoryCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const r of rows) if (r.kategoriya_id != null) acc.set(r.kategoriya_id, (acc.get(r.kategoriya_id) ?? 0) + 1)
    return acc
  }, [rows])
  const collectionCounts = useMemo(() => {
    const acc = new Map<string, number>()
    for (const r of rows) if (r.kollekciya) acc.set(r.kollekciya, (acc.get(r.kollekciya) ?? 0) + 1)
    return acc
  }, [rows])
  // W9.4 — season (tip_kollekcii) options derived from rows.
  const [selectedSeasons, setSelectedSeasons] = useState<Set<string>>(new Set())
  const seasonOptions = useMemo(() => {
    const acc = new Map<string, number>()
    for (const r of rows) {
      const s = (r.tip_kollekcii ?? "").trim()
      if (s) acc.set(s, (acc.get(s) ?? 0) + 1)
    }
    return Array.from(acc.entries())
      .sort(([a], [b]) => a.localeCompare(b, "ru"))
      .map(([value, count]) => ({ value, label: value, count }))
  }, [rows])
  const filtered = useMemo(() => {
    let res = rows
    if (selectedBrandIds.size > 0) res = res.filter((r) => r.brand_id != null && selectedBrandIds.has(r.brand_id))
    if (selectedStatusIds.size > 0) res = res.filter((r) => r.status_id != null && selectedStatusIds.has(r.status_id))
    if (selectedCategoryIds.size > 0) res = res.filter((r) => r.kategoriya_id != null && selectedCategoryIds.has(r.kategoriya_id))
    if (selectedCollectionNames.size > 0) res = res.filter((r) => r.kollekciya != null && selectedCollectionNames.has(r.kollekciya))
    if (selectedSeasons.size > 0) res = res.filter((r) => r.tip_kollekcii != null && selectedSeasons.has(r.tip_kollekcii))
    if (incompleteOnly) res = res.filter((r) => r.completeness < 0.5)
    return debouncedSearch.trim() ? res.filter((r) => modelMatches(r, debouncedSearch.trim().toLowerCase())) : res
  }, [rows, selectedBrandIds, selectedStatusIds, selectedCategoryIds, selectedCollectionNames, selectedSeasons, incompleteOnly, debouncedSearch])
  // W8.1 — apply sort AFTER filters.  Computed value resolver for keys that
  // aren't 1-to-1 with MatrixRow fields.
  const sortedFiltered = useMemo<MatrixRow[]>(() => {
    return sortRows(filtered as unknown as Record<string, unknown>[], (row, col) => {
      const r = row as unknown as MatrixRow
      switch (col) {
        case "nazvanie": return r.nazvanie_sayt ?? r.kod
        case "brand": return r.brand ?? ""
        case "kategoriya": return r.kategoriya ?? ""
        case "kollekciya": return r.kollekciya ?? ""
        case "fabrika": return r.fabrika ?? ""
        case "status": return r.status_id != null ? (statusNameById.get(r.status_id) ?? "") : ""
        case "completeness": return r.completeness
        case "cv_art_sku": return r.tovary_cnt
        case "obnovleno": return r.updated_at ?? ""
        default: return ""
      }
    }) as unknown as MatrixRow[]
  }, [filtered, sortRows, statusNameById])
  // Group filtered+sorted rows.  When groupBy === "none" we use the flat
  // sorted list directly so pagination below can slice it.
  const grouped = useMemo(() => {
    if (groupBy === "none") return [{ key: "_all", label: "", items: sortedFiltered }]
    const map = new Map<string, MatrixRow[]>()
    for (const r of sortedFiltered) {
      const k = getGroupKey(r, groupBy, statusNameById)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(r)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b, "ru")).map(([key, items]) => ({ key, label: key, items }))
  }, [sortedFiltered, groupBy, statusNameById])
  // W8.2 — Reset to page 1 whenever filters / sort / grouping change.
  useEffect(() => {
    resetPage()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, selectedBrandIds, selectedCategoryIds, selectedCollectionNames, selectedSeasons, selectedStatusIds, incompleteOnly, groupBy, sort.column, sort.direction])
  // Pagination only kicks in when groupBy === "none" (otherwise we render full
  // groups — pagination across groups is non-obvious UX).
  const paginated = useMemo(() => paginate(sortedFiltered), [paginate, sortedFiltered])
  const pagedGrouped = groupBy === "none"
    ? [{ key: "_all", label: "", items: paginated.slice }]
    : grouped
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
    } catch (err) { window.alert(translateError(err)) }
  }, [selectedKods, queryClient])
  const handleBulkDuplicate = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    for (const srcKod of kods) {
      const newKod = window.prompt(`Дублировать «${srcKod}»: введите новый kod`, `${srcKod}_copy`)
      if (!newKod) continue
      try { await duplicateModel(srcKod, newKod.trim()) } catch (err) { window.alert(translateError(err)) }
    }
    await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    setSelectedKods(new Set())
  }, [selectedKods, queryClient])
  const handleBulkArchive = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0 || !window.confirm(`Архивировать ${kods.length} модель(и) и все связанные вариации/артикулы/SKU?`)) return
    for (const kod of kods) {
      try { await archiveModel(kod) } catch (err) { window.alert(translateError(err)) }
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
    } catch (err) { window.alert(translateError(err)) }
  }, [queryClient])
  const handleRowArchive = useCallback(async (kod: string) => {
    if (!window.confirm(`Архивировать «${kod}» и все связанные вариации/артикулы/SKU?`)) return
    try {
      await archiveModel(kod)
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    } catch (err) { window.alert(translateError(err)) }
  }, [queryClient])
  const allVisibleSelected = filtered.length > 0 && filtered.every((r) => selectedKods.has(r.kod))
  // W7.3 — CSV-экспорт выбранных моделей через bulk-bar.
  const handleBulkExport = useCallback(() => {
    if (selectedKods.size === 0) return
    const selectedRows = filtered
      .filter((r) => selectedKods.has(r.kod))
      .map((r) => matrixRowToExport(r, statusNameById))
    downloadCsv({
      filename: `matrix-selected-${Date.now()}.csv`,
      rows: selectedRows,
      columns: MATRIX_EXPORT_COLUMNS,
    })
  }, [selectedKods, filtered, statusNameById])
  // W7.3 — регистрируем header-export текущей вкладки modeli_osnova
  // (filtered учитывает все applied chips/search/incompleteOnly).
  useEffect(() => {
    if (!onRegisterExport) return
    onRegisterExport(() => {
      const rowsForCsv = filtered.map((r) => matrixRowToExport(r, statusNameById))
      downloadCsv({
        filename: `matrix-${Date.now()}.csv`,
        rows: rowsForCsv,
        columns: MATRIX_EXPORT_COLUMNS,
      })
    })
    return () => onRegisterExport(null)
  }, [onRegisterExport, filtered, statusNameById])
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
            <ColumnsManager state={columnConfig} />
            <span className="text-xs text-stone-500 tabular-nums">{filtered.length} из {rows.length}</span>
          </div>
        </div>
        {/* W9.4 + W9.16 — compact Notion-style dropdown FilterBar.
            Объединяет бренд, категорию, коллекцию, сезон и статус в одну строку chip-ов. */}
        <div className="mb-3">
          <FilterBar
            filters={[
              {
                key: "brand",
                label: "Бренд",
                options: brendy.map((b) => ({ value: String(b.id), label: b.nazvanie, count: brandCounts.get(b.id) ?? 0 })),
              },
              {
                key: "kategoriya",
                label: "Категория",
                options: kategorii.map((k) => ({ value: String(k.id), label: k.nazvanie, count: categoryCounts.get(k.id) ?? 0 })),
              },
              {
                key: "status",
                label: "Статус",
                options: modelStatuses.map((s) => ({ value: String(s.id), label: s.nazvanie, count: statusCounts.get(s.id) ?? 0 })),
              },
              {
                key: "kollekciya",
                label: "Коллекция",
                options: kollekcii.map((k) => ({ value: k.nazvanie, label: k.nazvanie, count: collectionCounts.get(k.nazvanie) ?? 0 })),
              },
              {
                key: "season",
                label: "Сезон / тип коллекции",
                options: seasonOptions,
              },
            ]}
            values={{
              brand: Array.from(selectedBrandIds).map(String),
              kategoriya: Array.from(selectedCategoryIds).map(String),
              status: Array.from(selectedStatusIds).map(String),
              kollekciya: Array.from(selectedCollectionNames),
              season: Array.from(selectedSeasons),
            }}
            onChange={(key, next) => {
              if (key === "brand") setSelectedBrandIds(new Set(next.map((v) => Number(v))))
              else if (key === "kategoriya") setSelectedCategoryIds(new Set(next.map((v) => Number(v))))
              else if (key === "status") setSelectedStatusIds(new Set(next.map((v) => Number(v))))
              else if (key === "kollekciya") setSelectedCollectionNames(new Set(next))
              else if (key === "season") setSelectedSeasons(new Set(next))
            }}
            onResetAll={() => {
              setSelectedBrandIds(new Set())
              setSelectedCategoryIds(new Set())
              setSelectedStatusIds(new Set())
              setSelectedCollectionNames(new Set())
              setSelectedSeasons(new Set())
            }}
          />
        </div>
        {/* Table */}
        <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 32 }} />
              <col style={{ width: 40 }} />
              {MODEL_COLUMN_IDS.map((c) => (
                <col
                  key={c.id}
                  style={{
                    width: `${colWidths[c.id] ?? c.defaultWidth}px`,
                    display: isRenderColVisible(c.id) ? undefined : "none",
                  }}
                />
              ))}
              <col style={{ width: 40 }} />
            </colgroup>
            <thead className="bg-stone-50/80 border-b border-stone-200">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="px-2 py-2.5" />
                <th className="px-3 py-2.5"><input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAllVisible} style={{ accentColor: "#1C1917" }} className="rounded border-stone-300" aria-label="Выбрать все" /></th>
                {MODEL_COLUMNS.map(([label, cls, sortKey], idx) => {
                  const colId = MODEL_COLUMN_IDS[idx].id
                  const visible = isRenderColVisible(colId)
                  // W9.7 — первая (якорная) колонка «Название» — sticky.
                  const stickyCls = idx === 0 ? " cat-sticky-col cat-sticky-col-head" : ""
                  const baseCls = `relative px-3 py-2.5 font-medium ${cls ?? ""}${stickyCls}`
                  const hiddenStyle = !visible ? { display: "none" } : undefined
                  if (sortKey) {
                    return (
                      <SortableHeader
                        key={label}
                        active={sort.column === sortKey}
                        direction={sort.column === sortKey ? sort.direction : null}
                        onClick={() => toggleSort(sortKey)}
                        className={baseCls}
                        style={hiddenStyle}
                      >
                        {label}
                        <span {...bindResizer(colId)} />
                      </SortableHeader>
                    )
                  }
                  return (
                    <th key={label} className={baseCls} style={hiddenStyle}>
                      {label}
                      <span {...bindResizer(colId)} />
                    </th>
                  )
                })}
                <th className="px-2 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {pagedGrouped.map((group) => {
                const collapsed = groupBy !== "none" && isGroupCollapsed(group.key)
                return (
                <Fragment key={`group-${group.key}`}>
                  {groupBy !== "none" && (
                    <tr className="bg-stone-100/60 border-b border-stone-200">
                      <td colSpan={14} className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => toggleGroupCollapsed(group.key)}
                          className="flex items-center gap-2 w-full text-left hover:opacity-80 transition-opacity"
                          aria-expanded={!collapsed}
                          aria-label={collapsed ? `Развернуть группу ${group.label}` : `Свернуть группу ${group.label}`}
                        >
                          {collapsed ? <ChevronRight className="w-3.5 h-3.5 text-stone-500 shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-stone-500 shrink-0" />}
                          <span className="text-sm font-medium text-stone-800">{group.label}</span>
                          <span className="text-xs text-stone-500 tabular-nums">· {group.items.length}</span>
                        </button>
                      </td>
                    </tr>
                  )}
                  {!collapsed && group.items.map((m) => {
                    const canExpand = m.modeli.length >= 2
                    const isExpanded = expandedRows.has(m.id)
                    const checked = selectedKods.has(m.kod)
                    // W9.8 — Размеры берём из канонического `modeli_osnova.razmery_modeli`
                    // (то же поле, что редактируется в карточке модели). Раньше агрегатор
                    // собирал union по `modeli.rossiyskiy_razmer`, что было неверно: это
                    // российский numeric-код вариации, а не lettered ladder.
                    const variantSizes = new Set<string>(
                      m.razmery.map((s) => s.toUpperCase().trim()).filter(Boolean)
                    )
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
                          <td className="px-3 py-3 cursor-pointer cat-sticky-col" onClick={() => onOpen(m.kod)} style={!isRenderColVisible("nazvanie") ? { display: "none" } : undefined}>
                            <CellText className="font-medium text-stone-900 hover:underline font-mono" title={m.kod}>{m.kod}</CellText>
                            <CellText className="text-xs text-stone-500" title={m.nazvanie_sayt ?? ""}>{m.nazvanie_sayt || <span className="italic text-stone-400">без названия</span>}</CellText>
                          </td>
                          {/* W3.2 — Бренд */}
                          <td className="px-3 py-3 text-stone-700" style={!isRenderColVisible("brand") ? { display: "none" } : undefined}><CellText title={m.brand ?? ""}>{m.brand ?? <span className="text-stone-300">—</span>}</CellText></td>
                          <td className="px-3 py-3 text-stone-700" style={!isRenderColVisible("kategoriya") ? { display: "none" } : undefined}><CellText title={m.kategoriya ?? ""}>{m.kategoriya ?? "—"}</CellText></td>
                          <td className="px-3 py-3" style={!isRenderColVisible("kollekciya") ? { display: "none" } : undefined}>
                            <CellText className="text-stone-700" title={m.kollekciya ?? ""}>{m.kollekciya ?? "—"}</CellText>
                            <CellText className="text-[11px] text-stone-400" title={m.tip_kollekcii ?? ""}>{m.tip_kollekcii ?? ""}</CellText>
                          </td>
                          <td className="px-3 py-3 text-stone-700" style={!isRenderColVisible("fabrika") ? { display: "none" } : undefined}><CellText title={m.fabrika ?? ""}>{m.fabrika ?? "—"}</CellText></td>
                          <td className="px-3 py-3" style={!isRenderColVisible("status") ? { display: "none" } : undefined}><StatusBadge status={m.status_id != null ? statusById.get(m.status_id) ?? null : null} /></td>
                          <td className="px-3 py-3" style={!isRenderColVisible("razmery") ? { display: "none" } : undefined}><div className="flex items-center gap-0.5">{RAZMER_LADDER.map((sz) => <span key={sz} className={`text-[10px] px-1 py-0.5 rounded ${variantSizes.has(sz) ? "bg-stone-900 text-white" : "bg-stone-50 text-stone-300 ring-1 ring-inset ring-stone-200"}`}>{sz}</span>)}</div></td>
                          <td className="px-3 py-3" style={!isRenderColVisible("cveta") ? { display: "none" } : undefined}><ColorChips modelKod={m.kod} count={m.cveta_cnt} /></td>
                          <td className="px-3 py-3" style={!isRenderColVisible("zapoln") ? { display: "none" } : undefined}><Tooltip text={buildCompletenessTooltip(m)}><CompletenessRing value={m.completeness} size={16} hideLabel /></Tooltip></td>
                          <td className="px-3 py-3 text-right tabular-nums text-stone-600" style={!isRenderColVisible("cv_art_sku") ? { display: "none" } : undefined}>
                            <Tooltip text={`Цвета (привязанные к артикулам): ${m.cveta_cnt} · Артикулы: ${m.artikuly_cnt} · SKU: ${m.tovary_cnt}`}>
                              <span>
                                <span className="text-stone-900 font-medium">{m.cveta_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{m.artikuly_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{m.tovary_cnt}</span>
                              </span>
                            </Tooltip>
                          </td>
                          <td className="px-3 py-3 text-stone-500 text-xs" style={!isRenderColVisible("obnovleno") ? { display: "none" } : undefined}>{relativeDate(m.updated_at)}</td>
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
                          <tr key={`v-${v.id}`} className="cat-sticky-row-alt bg-stone-50/40 border-b border-stone-100 text-xs">
                            <td colSpan={2} />
                            <td className="pl-3 py-2 pr-3 cat-sticky-col" style={!isRenderColVisible("nazvanie") ? { display: "none" } : undefined}>
                              <div className="flex items-center gap-2 min-w-0"><div className="w-4 h-px bg-stone-300 shrink-0" /><CellText className="font-medium text-stone-800 font-mono" title={v.kod}>{v.kod}</CellText></div>
                              <CellText className="text-[11px] text-stone-500 ml-6 mt-0.5" title={v.nazvanie ?? ""}>{v.nazvanie}</CellText>
                            </td>
                            {/* W3.2 — Бренд (наследуется от модели — здесь пусто) */}
                            <td className="px-3 py-2 text-stone-300" style={!isRenderColVisible("brand") ? { display: "none" } : undefined}>—</td>
                            <td className="px-3 py-2 text-stone-400" style={!isRenderColVisible("kategoriya") ? { display: "none" } : undefined}>—</td>
                            <td className="px-3 py-2" style={!isRenderColVisible("kollekciya") ? { display: "none" } : undefined}>
                              <div className="flex items-center gap-1 text-stone-500 min-w-0"><Building2 className="w-3 h-3 text-stone-400 shrink-0" /><CellText title={v.importer_short ?? ""}>{v.importer_short ?? "—"}</CellText></div>
                            </td>
                            <td className="px-3 py-2 font-mono text-[11px] text-stone-500" style={!isRenderColVisible("fabrika") ? { display: "none" } : undefined}><CellText title={v.artikul_modeli ?? ""}>{v.artikul_modeli ?? "—"}</CellText></td>
                            <td className="px-3 py-2" style={!isRenderColVisible("status") ? { display: "none" } : undefined}><StatusBadge status={v.status_id != null ? statusById.get(v.status_id) ?? null : null} compact /></td>
                            <td className="px-3 py-2 text-stone-400 text-[10px]" style={!isRenderColVisible("razmery") ? { display: "none" } : undefined}>RU: {v.rossiyskiy_razmer ?? "—"}</td>
                            <td style={!isRenderColVisible("cveta") ? { display: "none" } : undefined} />
                            <td style={!isRenderColVisible("zapoln") ? { display: "none" } : undefined} />
                            <td className="px-3 py-2 text-right tabular-nums text-stone-600" style={!isRenderColVisible("cv_art_sku") ? { display: "none" } : undefined}><span className="text-stone-300">—</span><span className="text-stone-300 mx-1">/</span><span className="text-stone-700 font-medium">{v.artikuly_cnt}</span><span className="text-stone-300 mx-1">/</span><span>{v.tovary_cnt}</span></td>
                            <td className="px-3 py-2 text-stone-400" style={!isRenderColVisible("obnovleno") ? { display: "none" } : undefined}>—</td>
                            <td />
                          </tr>
                        ))}
                      </Fragment>
                    )
                  })}
                </Fragment>
                )
              })}
            </tbody>
          </table>
          {groupBy === "none" && (
            <Pagination
              page={paginated.page}
              totalPages={paginated.totalPages}
              total={paginated.total}
              pageSize={paginated.pageSize}
              onPage={setPage}
              onPageSize={(s) => { setPageSize(s); resetPage() }}
            />
          )}
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
          onExport={handleBulkExport}
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
type MatrixArtikulSortKey =
  | "artikul" | "model" | "variation" | "cvet" | "status" | "wb_nom" | "ozon" | "sku"
function ArtikulyTable({ onRegisterExport }: { onRegisterExport?: (fn: (() => void) | null) => void }) {
  const { data, isLoading } = useQuery({ queryKey: ["artikuly-registry"], queryFn: fetchArtikulyRegistry, staleTime: 5 * 60 * 1000 })
  const { widths: artWidths, bindResizer: bindArt } = useResizableColumns("matrix.artikuly", [...MATRIX_ARTIKULY_COLS])
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebouncedValue(search, 300)
  // W8.1 — sort state + ui_preferences persist.
  const { sort, toggleSort, setSortState, sortRows } = useTableSort<MatrixArtikulSortKey>()
  const sortLoadedRef = useRef(false)
  useEffect(() => {
    if (sortLoadedRef.current) return
    sortLoadedRef.current = true
    getUiPref<SortState<MatrixArtikulSortKey>>("matrix.artikuly", "sort").then((v) => {
      if (v && v.column != null && v.direction != null) setSortState(v)
    }).catch(() => { /* ignore */ })
  }, [setSortState])
  useEffect(() => {
    if (!sortLoadedRef.current) return
    setUiPref("matrix.artikuly", "sort", sort).catch(() => { /* non-fatal */ })
  }, [sort])
  // W8.2 — pagination.
  const { page, setPage, pageSize, setPageSize, paginate, resetPage } = usePagination(50)
  // W9.3 — расширенный поиск (артикул, модель, вариация, цвет RU/EN/код,
  // категория, коллекция, фабрика, WB ном., OZON артикул).
  const filtered = useMemo(() => {
    if (!data) return []
    const q = debouncedSearch.trim().toLowerCase()
    if (!q) return data
    return data.filter((a) => {
      const fields = [
        a.artikul,
        a.model_osnova_kod,
        a.model_kod,
        a.nazvanie_etiketka,
        a.cvet_color_code,
        a.cvet_nazvanie,
        a.color_en,
        a.kategoriya,
        a.kollekciya,
        a.fabrika,
        a.artikul_ozon,
        a.nomenklatura_wb != null ? String(a.nomenklatura_wb) : null,
      ]
      return fields.some(
        (f) => typeof f === "string" && f.length > 0 && f.toLowerCase().includes(q),
      )
    })
  }, [data, debouncedSearch])
  const sortedFiltered = useMemo(() => sortRows(
    filtered as unknown as Record<string, unknown>[],
    (row, col) => {
      const a = row as unknown as ArtikulRow
      switch (col) {
        case "artikul": return a.artikul
        case "model": return a.model_osnova_kod ?? ""
        case "variation": return a.model_kod ?? ""
        case "cvet": return a.cvet_color_code ?? ""
        case "status": return a.status_id ?? null
        case "wb_nom": return a.nomenklatura_wb ?? null
        case "ozon": return a.artikul_ozon ?? ""
        case "sku": return a.tovary_cnt
        default: return ""
      }
    },
  ) as unknown as ArtikulRow[], [filtered, sortRows])
  useEffect(() => { resetPage() }, [search, sort.column, sort.direction, resetPage])
  const paginated = useMemo(() => paginate(sortedFiltered), [paginate, sortedFiltered])
  // W7.3 — header-export: текущий filtered (search учитывается).
  useEffect(() => {
    if (!onRegisterExport) return
    onRegisterExport(() => {
      const rowsForCsv = filtered.map((a) => ({
        artikul: a.artikul,
        model_osnova_kod: a.model_osnova_kod ?? "",
        model_kod: a.model_kod ?? "",
        cvet_color_code: a.cvet_color_code ?? "",
        cvet_nazvanie: a.cvet_nazvanie ?? "",
        status_id: a.status_id ?? "",
        nomenklatura_wb: a.nomenklatura_wb ?? "",
        artikul_ozon: a.artikul_ozon ?? "",
        tovary_cnt: a.tovary_cnt,
      }))
      downloadCsv({
        filename: `artikuly-${Date.now()}.csv`,
        rows: rowsForCsv,
        columns: [
          { key: "artikul", label: "Артикул" },
          { key: "model_osnova_kod", label: "Модель" },
          { key: "model_kod", label: "Вариация" },
          { key: "cvet_color_code", label: "Цвет (код)" },
          { key: "cvet_nazvanie", label: "Цвет" },
          { key: "status_id", label: "Статус" },
          { key: "nomenklatura_wb", label: "WB номенкл." },
          { key: "artikul_ozon", label: "OZON артикул" },
          { key: "tovary_cnt", label: "SKU" },
        ],
      })
    })
    return () => onRegisterExport(null)
  }, [onRegisterExport, filtered])
  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      <RegistryTop search={search} setSearch={setSearch} placeholder="Артикул, модель, цвет…" count={filtered.length} total={data?.length ?? 0} />
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
          <colgroup>
            {MATRIX_ARTIKULY_COLS.map((c) => (
              <col key={c.id} style={{ width: `${artWidths[c.id] ?? c.defaultWidth}px` }} />
            ))}
          </colgroup>
          <RegistryHead
            labels={["Артикул", "Модель", "Вариация", "Цвет", "Статус", "WB номенкл.", "OZON", "SKU"]}
            rightLabel="SKU"
            columnIds={MATRIX_ARTIKULY_COLS.map((c) => c.id)}
            bindResizer={bindArt}
            sortKeys={["artikul", "model", "variation", "cvet", "status", "wb_nom", "ozon", "sku"]}
            sortColumn={sort.column}
            sortDirection={sort.direction}
            onSort={(k) => toggleSort(k as MatrixArtikulSortKey)}
            stickyFirst
          />
          <tbody>
            {paginated.slice.map((a) => (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-900 cat-sticky-col"><CellText title={a.artikul}>{a.artikul}</CellText></td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs"><CellText title={a.model_osnova_kod ?? ""}>{a.model_osnova_kod ?? "—"}</CellText></td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600"><CellText title={a.model_kod ?? ""}>{a.model_kod ?? "—"}</CellText></td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <ColorSwatch colorCode={a.cvet_color_code} size={14} />
                    <CellText className="font-mono text-xs text-stone-700" title={a.cvet_color_code ?? ""}>{a.cvet_color_code ?? "—"}</CellText>
                    <CellText className="text-stone-500 text-xs" title={a.cvet_nazvanie ?? ""}>{a.cvet_nazvanie}</CellText>
                  </div>
                </td>
                <td className="px-3 py-2.5"><StatusBadge statusId={a.status_id ?? 0} compact /></td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500 tabular-nums"><CellText title={a.nomenklatura_wb != null ? String(a.nomenklatura_wb) : ""}>{a.nomenklatura_wb ?? "—"}</CellText></td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500"><CellText title={a.artikul_ozon ?? ""}>{a.artikul_ozon ?? "—"}</CellText></td>
                <td className="px-3 py-2.5 text-right tabular-nums text-stone-700">{a.tovary_cnt}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination
          page={paginated.page}
          totalPages={paginated.totalPages}
          total={paginated.total}
          pageSize={paginated.pageSize}
          onPage={setPage}
          onPageSize={(s) => { setPageSize(s); resetPage() }}
        />
      </div>
    </div>
  )
}
// ─── Tovary registry tab ───────────────────────────────────────────────────
const CHANNELS = [
  { id: "all", label: "Все" }, { id: "wb", label: "WB" }, { id: "ozon", label: "Ozon" }, { id: "sayt", label: "Сайт" }, { id: "lamoda", label: "Lamoda" },
] as const
type MatrixTovarSortKey =
  | "barkod" | "model" | "variation" | "cvet" | "razmer" | "wb" | "ozon" | "sayt" | "lamoda"
function TovaryTable({ onRegisterExport }: { onRegisterExport?: (fn: (() => void) | null) => void }) {
  const { data, isLoading } = useQuery({ queryKey: ["tovary-registry"], queryFn: fetchTovaryRegistry, staleTime: 5 * 60 * 1000 })
  const { widths: tovWidths, bindResizer: bindTov } = useResizableColumns("matrix.tovary", [...MATRIX_TOVARY_COLS])
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebouncedValue(search, 300)
  const [channelFilter, setChannelFilter] = useState<(typeof CHANNELS)[number]["id"]>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
  const productStatuses = CATALOG_STATUSES.filter((s) => s.tip === "product")
  // W8.1 — sort state + ui_preferences persist.
  const { sort, toggleSort, setSortState, sortRows } = useTableSort<MatrixTovarSortKey>()
  const sortLoadedRef = useRef(false)
  useEffect(() => {
    if (sortLoadedRef.current) return
    sortLoadedRef.current = true
    getUiPref<SortState<MatrixTovarSortKey>>("matrix.tovary", "sort").then((v) => {
      if (v && v.column != null && v.direction != null) setSortState(v)
    }).catch(() => { /* ignore */ })
  }, [setSortState])
  useEffect(() => {
    if (!sortLoadedRef.current) return
    setUiPref("matrix.tovary", "sort", sort).catch(() => { /* non-fatal */ })
  }, [sort])
  // W8.2 — pagination.
  const { page, setPage, pageSize, setPageSize, paginate, resetPage } = usePagination(50)
  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (channelFilter === "wb") res = res.filter((t) => t.status_id !== null)
    else if (channelFilter === "ozon") res = res.filter((t) => t.status_ozon_id !== null)
    else if (channelFilter === "sayt") res = res.filter((t) => t.status_sayt_id !== null)
    else if (channelFilter === "lamoda") res = res.filter((t) => t.status_lamoda_id !== null)
    if (statusFilter !== "all") res = res.filter((t) => t.status_id === statusFilter || t.status_ozon_id === statusFilter || t.status_sayt_id === statusFilter || t.status_lamoda_id === statusFilter)
    const q = debouncedSearch.trim().toLowerCase()
    if (!q) return res
    // W9.3 — расширенный поиск по баркоду (+gs1/gs2/переход), артикулу,
    // моделям, цвету (RU/EN/код), размеру, WB ном., OZON, коллекции, категории.
    return res.filter((t) => {
      const fields = [
        t.barkod,
        t.barkod_gs1,
        t.barkod_gs2,
        t.barkod_perehod,
        t.artikul,
        t.model_osnova_kod,
        t.model_kod,
        t.nazvanie_etiketka,
        t.cvet_color_code,
        t.cvet_ru,
        t.color_en,
        t.razmer,
        t.razmer_kod,
        t.kollekciya,
        t.kategoriya,
        t.artikul_ozon,
        t.nomenklatura_wb != null ? String(t.nomenklatura_wb) : null,
      ]
      return fields.some(
        (f) => typeof f === "string" && f.length > 0 && f.toLowerCase().includes(q),
      )
    })
  }, [data, channelFilter, statusFilter, debouncedSearch])
  const sortedFiltered = useMemo(() => sortRows(
    filtered as unknown as Record<string, unknown>[],
    (row, col) => {
      const t = row as unknown as TovarRow
      switch (col) {
        case "barkod": return t.barkod
        case "model": return t.model_osnova_kod ?? ""
        case "variation": return t.model_kod ?? ""
        case "cvet": return t.cvet_color_code ?? ""
        case "razmer": return t.razmer ?? ""
        case "wb": return t.status_id ?? null
        case "ozon": return t.status_ozon_id ?? null
        case "sayt": return t.status_sayt_id ?? null
        case "lamoda": return t.status_lamoda_id ?? null
        default: return ""
      }
    },
  ) as unknown as TovarRow[], [filtered, sortRows])
  useEffect(() => {
    resetPage()
  }, [channelFilter, statusFilter, search, sort.column, sort.direction, resetPage])
  const paginated = useMemo(() => paginate(sortedFiltered), [paginate, sortedFiltered])
  // W7.3 — header-export: текущий filtered (channel + status + search учтены).
  useEffect(() => {
    if (!onRegisterExport) return
    onRegisterExport(() => {
      const rowsForCsv = filtered.map((t) => ({
        barkod: t.barkod,
        model_osnova_kod: t.model_osnova_kod ?? "",
        model_kod: t.model_kod ?? "",
        cvet_color_code: t.cvet_color_code ?? "",
        razmer: t.razmer ?? "",
        status_wb: t.status_id ?? "",
        status_ozon: t.status_ozon_id ?? "",
        status_sayt: t.status_sayt_id ?? "",
        status_lamoda: t.status_lamoda_id ?? "",
      }))
      downloadCsv({
        filename: `tovary-${Date.now()}.csv`,
        rows: rowsForCsv,
        columns: [
          { key: "barkod", label: "Баркод" },
          { key: "model_osnova_kod", label: "Модель" },
          { key: "model_kod", label: "Вариация" },
          { key: "cvet_color_code", label: "Цвет" },
          { key: "razmer", label: "Размер" },
          { key: "status_wb", label: "Статус WB" },
          { key: "status_ozon", label: "Статус OZON" },
          { key: "status_sayt", label: "Статус Сайт" },
          { key: "status_lamoda", label: "Статус Lamoda" },
        ],
      })
    })
    return () => onRegisterExport(null)
  }, [onRegisterExport, filtered])
  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      {/* Channel tabs */}
      <div className="flex items-center gap-1 mb-3">
        {CHANNELS.map((c) => <button key={c.id} onClick={() => setChannelFilter(c.id)} className={`px-3 py-1.5 text-xs rounded-md transition-colors ${channelFilter === c.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}>{c.label}</button>)}
        <div className="h-4 w-px bg-stone-200 mx-1" />
        <select value={statusFilter === "all" ? "all" : String(statusFilter)} onChange={(e) => setStatusFilter(e.target.value === "all" ? "all" : Number(e.target.value))} className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none">
          <option value="all">Все статусы</option>
          {productStatuses.map((s) => <option key={s.id} value={s.id}>{s.nazvanie}</option>)}
        </select>
      </div>
      {/* Search + count */}
      <RegistryTop search={search} setSearch={setSearch} placeholder="Баркод, модель, артикул…" count={filtered.length} total={data?.length ?? 0} />
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
          <colgroup>
            {MATRIX_TOVARY_COLS.map((c) => (
              <col key={c.id} style={{ width: `${tovWidths[c.id] ?? c.defaultWidth}px` }} />
            ))}
          </colgroup>
          <RegistryHead
            labels={["Баркод", "Модель", "Вариация", "Цвет", "Размер", "WB", "OZON", "Сайт", "Lamoda"]}
            borderedLabel="WB"
            columnIds={MATRIX_TOVARY_COLS.map((c) => c.id)}
            bindResizer={bindTov}
            sortKeys={["barkod", "model", "variation", "cvet", "razmer", "wb", "ozon", "sayt", "lamoda"]}
            sortColumn={sort.column}
            sortDirection={sort.direction}
            onSort={(k) => toggleSort(k as MatrixTovarSortKey)}
            stickyFirst
          />
          <tbody>
            {paginated.slice.map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-700 cat-sticky-col"><CellText title={t.barkod}>{t.barkod}</CellText></td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs"><CellText title={t.model_osnova_kod ?? ""}>{t.model_osnova_kod ?? "—"}</CellText></td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600"><CellText title={t.model_kod ?? ""}>{t.model_kod ?? "—"}</CellText></td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5 min-w-0"><ColorSwatch colorCode={t.cvet_color_code} size={14} /><CellText className="font-mono text-xs" title={t.cvet_color_code ?? ""}>{t.cvet_color_code ?? "—"}</CellText></div>
                </td>
                <td className="px-3 py-2.5 font-mono text-xs"><CellText title={t.razmer ?? ""}>{t.razmer ?? "—"}</CellText></td>
                <td className="px-3 py-2.5 border-l border-stone-100"><StatusBadge statusId={t.status_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_ozon_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_sayt_id ?? 0} compact /></td>
                <td className="px-3 py-2.5"><StatusBadge statusId={t.status_lamoda_id ?? 0} compact /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination
          page={paginated.page}
          totalPages={paginated.totalPages}
          total={paginated.total}
          pageSize={paginated.pageSize}
          onPage={setPage}
          onPageSize={(s) => { setPageSize(s); resetPage() }}
        />
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
function RegistryHead({
  labels, rightLabel, borderedLabel, columnIds, bindResizer,
  sortKeys, sortColumn, sortDirection, onSort, stickyFirst,
}: {
  labels: string[]
  rightLabel?: string
  borderedLabel?: string
  columnIds?: readonly string[]
  bindResizer?: (id: string) => ResizerBindings
  /** Same length as labels; null means «not sortable». */
  sortKeys?: readonly (string | null)[]
  sortColumn?: string | null
  sortDirection?: "asc" | "desc" | null
  onSort?: (key: string) => void
  /** W9.7 — pin the first header cell to `left: 0`. */
  stickyFirst?: boolean
}) {
  return (
    <thead className="bg-stone-50/80 border-b border-stone-200">
      <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
        {labels.map((label, idx) => {
          const colId = columnIds?.[idx]
          const sortKey = sortKeys?.[idx] ?? null
          const stickyCls = stickyFirst && idx === 0 ? " cat-sticky-col cat-sticky-col-head" : ""
          const baseCls = `relative px-3 py-2.5 font-medium ${label === rightLabel ? "text-right" : ""} ${label === borderedLabel ? "border-l border-stone-200" : ""}${stickyCls}`
          if (sortKey && onSort) {
            return (
              <SortableHeader
                key={label}
                active={sortColumn === sortKey}
                direction={sortColumn === sortKey ? (sortDirection ?? null) : null}
                onClick={() => onSort(sortKey)}
                className={baseCls}
              >
                {label}
                {colId && bindResizer && <span {...bindResizer(colId)} />}
              </SortableHeader>
            )
          }
          return (
            <th key={label} className={baseCls}>
              {label}
              {colId && bindResizer && <span {...bindResizer(colId)} />}
            </th>
          )
        })}
      </tr>
    </thead>
  )
}
// Column IDs + default widths for the inline registry tables (matrix tabs Artikuly/Tovary).
const MATRIX_ARTIKULY_COLS = [
  { id: "artikul", defaultWidth: 130 },
  { id: "model", defaultWidth: 110 },
  { id: "variation", defaultWidth: 130 },
  { id: "cvet", defaultWidth: 180 },
  { id: "status", defaultWidth: 130 },
  { id: "wb_nom", defaultWidth: 120 },
  { id: "ozon", defaultWidth: 120 },
  { id: "sku", defaultWidth: 70 },
] as const
const MATRIX_TOVARY_COLS = [
  { id: "barkod", defaultWidth: 140 },
  { id: "model", defaultWidth: 110 },
  { id: "variation", defaultWidth: 130 },
  { id: "cvet", defaultWidth: 140 },
  { id: "razmer", defaultWidth: 70 },
  { id: "wb", defaultWidth: 110 },
  { id: "ozon", defaultWidth: 110 },
  { id: "sayt", defaultWidth: 110 },
  { id: "lamoda", defaultWidth: 110 },
] as const
// ─── Main MatrixPage ───────────────────────────────────────────────────────
export function MatrixPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [listTab, setListTab] = useState<ListTab>("modeli_osnova")
  const queryClient = useQueryClient()
  const matrixQ = useQuery({ queryKey: ["matrix-list"], queryFn: fetchMatrixList, staleTime: 3 * 60 * 1000 })
  // W3.2 — brendy для chip-filter в шапке матрицы.
  const brendyQ = useQuery({ queryKey: ["catalog", "brendy"], queryFn: fetchBrendy, staleTime: 10 * 60 * 1000 })
  const kategoriiQ = useQuery({ queryKey: ["kategorii"], queryFn: fetchKategorii, staleTime: 10 * 60 * 1000 })
  const kollekciiQ = useQuery({ queryKey: ["kollekcii"], queryFn: fetchKollekcii, staleTime: 10 * 60 * 1000 })
  const statusyQ = useQuery({ queryKey: ["statusy"], queryFn: fetchStatusy, staleTime: 30 * 60 * 1000 })
  const openModel = useCallback((kod: string) => {
    const next = new URLSearchParams(searchParams)
    next.set("model", kod)
    next.delete("id")
    setSearchParams(next)
  }, [searchParams, setSearchParams])
  // W4.1: открытие модалки «+ Новая модель». Реальное создание — внутри
  // <NewModelModal>, после успеха срабатывает onCreated → navigate в карточку.
  const [newModelOpen, setNewModelOpen] = useState(false)
  const handleNewModel = useCallback(() => {
    setNewModelOpen(true)
  }, [])
  const handleNewModelCreated = useCallback(async (createdKod: string) => {
    await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    setNewModelOpen(false)
    const next = new URLSearchParams(searchParams)
    next.set("model", createdKod)
    next.delete("id")
    setSearchParams(next)
  }, [queryClient, searchParams, setSearchParams])
  // W7.3 — header «Экспорт» делегируется активной вкладке.  Inner-таблица
  // регистрирует свою callback через onRegisterExport, header кликает по ref.
  const exportRef = useRef<(() => void) | null>(null)
  const registerExport = useCallback((fn: (() => void) | null) => {
    exportRef.current = fn
  }, [])
  const handleHeaderExport = useCallback(() => {
    if (exportRef.current) {
      exportRef.current()
    } else {
      window.alert("Экспорт недоступен для текущей вкладки")
    }
  }, [])
  // ?model=KOD opens B3's <ModelCardModal /> as overlay from CatalogLayout.
  const rows = matrixQ.data ?? []
  const brendy = brendyQ.data ?? []
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
            <button onClick={handleHeaderExport} className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 border border-stone-200"><Download className="w-3.5 h-3.5" /> Экспорт</button>
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
          <ModeliOsnovaTable rows={rows} brendy={brendy} kategorii={kategorii} kollekcii={kollekcii} modelStatuses={modelStatuses} onOpen={openModel} onRegisterExport={registerExport} />
        )}
        {listTab === "artikuly" && <ArtikulyTable onRegisterExport={registerExport} />}
        {listTab === "tovary" && <TovaryTable onRegisterExport={registerExport} />}
      </div>
      {/* W4.1: модалка «+ Новая модель» вместо window.prompt. */}
      <NewModelModal
        isOpen={newModelOpen}
        onClose={() => setNewModelOpen(false)}
        onCreated={handleNewModelCreated}
      />
    </div>
  )
}
