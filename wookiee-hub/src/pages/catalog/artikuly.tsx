import { useMemo, useState, useCallback, useEffect, useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Search, X, ChevronDown, Loader2 } from "lucide-react"
import {
  fetchArtikulyRegistry, fetchStatusy, bulkUpdateArtikulStatus,
  fetchRazmery, fetchTovaryByArtikul, insertTovar,
  getUiPref, setUiPref,
  type ArtikulRow, type ArtikulTovar, type Razmer,
} from "@/lib/catalog/service"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { ColumnsManager, type ColumnDef } from "@/components/catalog/ui/columns-manager"
import { SortableHeader } from "@/components/catalog/ui/sortable-header"
import { Pagination } from "@/components/catalog/ui/pagination"
import { RefModal } from "@/components/catalog/ui/ref-modal"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { useResizableColumns } from "@/hooks/use-resizable-columns"
import { useTableSort, type SortState } from "@/hooks/use-table-sort"
import { usePagination } from "@/hooks/use-pagination"
import { downloadCsv } from "@/lib/catalog/csv-export"

// Default per-column widths (px) for the standalone Артикулы page (W1.5).
// Keys must match ARTIKULY_COLUMNS[i].key.
const ARTIKULY_DEFAULT_WIDTHS: Record<string, number> = {
  artikul: 160,
  model: 140,
  cvet: 180,
  status: 140,
  wb_nom: 130,
  ozon_art: 140,
  created: 110,
  updated: 110,
  kategoriya: 130,
  kollekciya: 140,
  fabrika: 140,
}

// 11 columns; all default-visible per Final Report MINOR fix.
const ARTIKULY_COLUMNS: ColumnDef[] = [
  { key: "artikul",         label: "Артикул",         default: true },
  { key: "model",           label: "Модель",          default: true },
  { key: "cvet",            label: "Цвет",            default: true },
  { key: "status",          label: "Статус артикула", default: true },
  { key: "wb_nom",          label: "WB-номенклатура", default: true },
  { key: "ozon_art",        label: "OZON-артикул",    default: true },
  { key: "created",         label: "Создан",          default: true },
  { key: "updated",         label: "Обновлён",        default: true },
  { key: "kategoriya",      label: "Категория",       default: true },
  { key: "kollekciya",      label: "Коллекция",       default: true },
  { key: "fabrika",         label: "Производитель",   default: true },
]

const DEFAULT_COLUMNS = ARTIKULY_COLUMNS.filter((c) => c.default).map((c) => c.key)

// W8.1 — sort keys must match column keys above.
type ArtikulSortKey =
  | "artikul" | "model" | "cvet" | "status" | "wb_nom" | "ozon_art"
  | "created" | "updated" | "kategoriya" | "kollekciya" | "fabrika"
const ARTIKULY_SORTABLE: ReadonlySet<string> = new Set<ArtikulSortKey>([
  "artikul", "model", "cvet", "status", "wb_nom", "ozon_art",
  "created", "updated", "kategoriya", "kollekciya", "fabrika",
])
function getArtikulSortValue(a: ArtikulRow, col: ArtikulSortKey): unknown {
  switch (col) {
    case "artikul": return a.artikul
    case "model": return a.model_osnova_kod ?? ""
    case "cvet": return a.cvet_color_code ?? ""
    case "status": return a.status_id ?? null
    case "wb_nom": return a.nomenklatura_wb ?? null
    case "ozon_art": return a.artikul_ozon ?? ""
    case "created": return a.created_at ?? ""
    case "updated": return a.updated_at ?? ""
    case "kategoriya": return a.kategoriya ?? ""
    case "kollekciya": return a.kollekciya ?? ""
    case "fabrika": return a.fabrika ?? ""
  }
}

// ─── Inline status popover (W8.5) ─────────────────────────────────────────

interface ArtikulStatusOption {
  id: number
  nazvanie: string
  color: string | null
}

interface InlineArtikulStatusCellProps {
  /** Текущий status_id (null если не выставлен). */
  currentStatusId: number | null
  /** Список опций tip='artikul'. */
  statusOptions: ArtikulStatusOption[]
  /** Применить статус. */
  onChange: (statusId: number) => Promise<void>
}

/**
 * InlineArtikulStatusCell — popover-редактор статуса артикула.
 * Открывается кликом по бейджу, закрывается mousedown-outside / Escape.
 * Артикул не имеет каналов → один список опций.
 */
function InlineArtikulStatusCell({
  currentStatusId, statusOptions, onChange,
}: InlineArtikulStatusCellProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDoc)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const onSelect = useCallback(async (id: number) => {
    if (saving) return
    setSaving(true)
    try {
      await onChange(id)
      setOpen(false)
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`Не удалось обновить статус: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }, [onChange, saving])

  return (
    <div className="relative inline-block" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="hover:ring-1 hover:ring-stone-400 rounded-md transition-all"
        title="Кликните, чтобы изменить статус"
      >
        {currentStatusId != null
          ? <StatusBadge statusId={currentStatusId} compact />
          : <span className="text-[11px] text-stone-400 italic px-1.5 py-px">—</span>}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-stone-200 rounded-lg shadow-lg z-30">
          <div className="p-2 border-b border-stone-100 flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-wider text-stone-400">
              Статус артикула
            </div>
            {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin" />}
          </div>
          <div className="p-1 max-h-72 overflow-y-auto">
            {statusOptions.length === 0 && (
              <div className="px-2 py-3 text-xs text-stone-400 italic">Нет статусов</div>
            )}
            {statusOptions.map((s) => (
              <button
                key={s.id}
                type="button"
                disabled={saving}
                onClick={() => onSelect(s.id)}
                className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-stone-50 rounded text-left disabled:opacity-50"
              >
                <StatusBadge status={{ nazvanie: s.nazvanie, color: s.color ?? "gray" }} compact />
                {s.id === currentStatusId && (
                  <span className="ml-auto text-[10px] text-emerald-600">текущий</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Drill-down overlay (W8.4) ─────────────────────────────────────────────
//
// Overlay-карточка артикула: header (артикул + цвет + вариация + статус),
// read-only список SKU (баркод, размер, статусы по 4 каналам) и кнопка «+ SKU».
//
// SKU грузятся отдельным запросом `fetchTovaryByArtikul` (cached на `artikulId`)
// — registry-данные (`tovary_cnt`) дают только число.  Кнопка «+ SKU» открывает
// RefModal (см. TabSKU в model-card.tsx за образцом), на submit вызывает
// `insertTovar(artikulId, razmerId)` и инвалидирует обе query-keys.
//
// Inline-edit статусов в этом overlay НЕ делается — read-only.  Inline-edit
// статусов SKU — territory W8.5 (tovary-реестр).

interface ArtikulDrillDownProps {
  row: ArtikulRow
  /** Все статусы (из родительского fetchStatusy) — для бейджей и id→label fallback. */
  statusyData?: { id: number; nazvanie: string; tip: string; color: string | null }[]
  onClose: () => void
}

function ArtikulDrillDown({ row, statusyData, onClose }: ArtikulDrillDownProps) {
  const queryClient = useQueryClient()
  const [addSkuOpen, setAddSkuOpen] = useState(false)

  // SKU артикула — отдельный запрос (registry содержит только tovary_cnt).
  const tovaryQ = useQuery({
    queryKey: ["tovary-by-artikul", row.id],
    queryFn: () => fetchTovaryByArtikul(row.id),
    staleTime: 30 * 1000,
  })
  const tovary: ArtikulTovar[] = tovaryQ.data ?? []

  // Размеры — для select-поля в RefModal «+ SKU».
  const razmeryQ = useQuery({
    queryKey: ["catalog", "razmery"],
    queryFn: fetchRazmery,
    staleTime: 5 * 60 * 1000,
  })
  const razmery: Razmer[] = razmeryQ.data ?? []

  // Map status_id → {nazvanie, color} — единая lookup для SKU-таблицы.
  const statusById = useMemo(() => {
    const m = new Map<number, { nazvanie: string; color: string | null }>()
    for (const s of statusyData ?? []) m.set(s.id, { nazvanie: s.nazvanie, color: s.color })
    return m
  }, [statusyData])

  // razmer_id, которые уже заняты у этого артикула (скрываем в select-опциях).
  const usedRazmerIds = useMemo(() => {
    const s = new Set<number>()
    for (const t of tovary) if (t.razmer_id != null) s.add(t.razmer_id)
    return s
  }, [tovary])

  const razmerOptions = useMemo(
    () =>
      razmery
        .filter((r) => !usedRazmerIds.has(r.id))
        .map((r) => ({ value: r.id, label: r.nazvanie ?? `#${r.id}` })),
    [razmery, usedRazmerIds],
  )

  const insertMut = useMutation({
    mutationFn: ({ razmerId }: { razmerId: number }) => insertTovar(row.id, razmerId),
    onSuccess: () => {
      setAddSkuOpen(false)
      void queryClient.invalidateQueries({ queryKey: ["tovary-by-artikul", row.id] })
      void queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
    },
  })

  // Esc закрывает overlay (если не открыта вложенная RefModal — она сама Esc обрабатывает).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !addSkuOpen) onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose, addSkuOpen])

  // Helper — отрисовать статус SKU через справочник (поддерживает любой id).
  function renderSkuStatus(statusId: number | null): React.ReactNode {
    if (statusId == null) {
      return <span className="text-[11px] text-stone-400 italic">—</span>
    }
    const s = statusById.get(statusId)
    if (!s) return <span className="text-[11px] text-stone-500 font-mono">#{statusId}</span>
    return (
      <StatusBadge
        status={{ nazvanie: s.nazvanie, color: s.color ?? "gray" }}
        compact
        size="sm"
      />
    )
  }

  const swatch = row.cvet_hex ?? swatchColor(row.cvet_color_code ?? "")
  const artikulStatus = row.status_id != null ? statusById.get(row.status_id) : null

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/30 flex items-start justify-center px-4 py-10"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) onClose()
        }}
      >
        <div
          className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden"
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-5 pt-4 pb-3 border-b border-stone-200 flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">
                Артикул
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-2xl text-stone-900 cat-font-serif font-mono">
                  {row.artikul}
                </h2>
                {artikulStatus && (
                  <StatusBadge
                    status={{ nazvanie: artikulStatus.nazvanie, color: artikulStatus.color ?? "gray" }}
                  />
                )}
              </div>
              <div className="mt-2 flex items-center gap-4 flex-wrap text-xs text-stone-600">
                <div className="flex items-center gap-1.5">
                  <ColorSwatch hex={swatch} size={14} />
                  <span className="font-mono">{row.cvet_color_code ?? "—"}</span>
                  {row.cvet_nazvanie && (
                    <span className="text-stone-500">· {row.cvet_nazvanie}</span>
                  )}
                </div>
                {row.model_kod && (
                  <div>
                    <span className="text-stone-400">Вариация: </span>
                    <span className="font-mono text-stone-700">{row.model_kod}</span>
                  </div>
                )}
                {row.model_osnova_kod && (
                  <div>
                    <span className="text-stone-400">Модель: </span>
                    <span className="font-mono text-stone-700">{row.model_osnova_kod}</span>
                  </div>
                )}
                {row.nazvanie_etiketka && (
                  <div className="text-stone-500">{row.nazvanie_etiketka}</div>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-md"
              aria-label="Закрыть"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* SKU section */}
          <div className="flex-1 overflow-auto">
            <div className="px-5 py-3 flex items-center justify-between gap-3">
              <div>
                <div className="font-medium text-stone-900 text-sm">SKU артикула</div>
                <div className="text-xs text-stone-500">
                  {tovaryQ.isLoading
                    ? "Загрузка…"
                    : `${tovary.length} SKU · read-only`}
                </div>
              </div>
              <button
                type="button"
                className="px-2.5 py-1 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={razmerOptions.length === 0 || razmeryQ.isLoading}
                onClick={() => setAddSkuOpen(true)}
                title={
                  razmerOptions.length === 0
                    ? "Все размеры из справочника уже добавлены"
                    : "Создать новый SKU"
                }
              >
                <Plus className="w-3 h-3" /> SKU
              </button>
            </div>
            <div className="px-5 pb-5">
              <div className="border border-stone-200 rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-stone-50/80 border-b border-stone-200">
                    <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                      <th className="px-3 py-2 font-medium">Баркод</th>
                      <th className="px-3 py-2 font-medium">Размер</th>
                      <th className="px-3 py-2 font-medium border-l border-stone-200">WB</th>
                      <th className="px-3 py-2 font-medium">OZON</th>
                      <th className="px-3 py-2 font-medium">Сайт</th>
                      <th className="px-3 py-2 font-medium">Lamoda</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tovaryQ.isLoading && (
                      <tr>
                        <td colSpan={6} className="px-3 py-8 text-center text-stone-400">
                          <Loader2 className="w-4 h-4 inline animate-spin mr-2" />
                          Загрузка SKU…
                        </td>
                      </tr>
                    )}
                    {!tovaryQ.isLoading && tovary.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-3 py-8 text-center text-sm text-stone-400 italic">
                          Нет SKU для этого артикула
                        </td>
                      </tr>
                    )}
                    {!tovaryQ.isLoading && tovary.map((t) => (
                      <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                        <td className="px-3 py-2 font-mono text-xs text-stone-700">{t.barkod}</td>
                        <td className="px-3 py-2 font-mono text-xs">{t.razmer_nazvanie ?? "—"}</td>
                        <td className="px-3 py-2 border-l border-stone-100">{renderSkuStatus(t.status_id)}</td>
                        <td className="px-3 py-2">{renderSkuStatus(t.status_ozon_id)}</td>
                        <td className="px-3 py-2">{renderSkuStatus(t.status_sayt_id)}</td>
                        <td className="px-3 py-2">{renderSkuStatus(t.status_lamoda_id)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {tovaryQ.error && (
                <div className="mt-2 text-xs text-red-500">
                  Ошибка загрузки SKU: {(tovaryQ.error as Error).message}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Модалка «+ SKU» — один размер, артикул фиксирован контекстом. */}
      {addSkuOpen && (
        <RefModal
          title={`Создать SKU для ${row.artikul}`}
          fields={[
            {
              key: "razmer_id",
              label: "Размер",
              type: "select",
              required: true,
              options: razmerOptions,
              full: true,
              hint: "Свободный размер. Уже занятые скрыты.",
            },
          ]}
          onSave={async (vals) => {
            const razmerId = Number(vals.razmer_id)
            if (!Number.isFinite(razmerId)) return
            await insertMut.mutateAsync({ razmerId })
          }}
          onCancel={() => setAddSkuOpen(false)}
          saveLabel="Создать"
        />
      )}
    </>
  )
}

function renderCell(key: string, a: ArtikulRow): React.ReactNode {
  switch (key) {
    case "artikul":
      return <span className="font-mono text-xs text-stone-900">{a.artikul}</span>
    case "model":
      return (
        <div className="flex flex-col">
          <span className="font-mono text-xs font-medium text-stone-900">
            {a.model_osnova_kod ?? "—"}
          </span>
          {a.nazvanie_etiketka && (
            <span className="text-[11px] text-stone-500">{a.nazvanie_etiketka}</span>
          )}
        </div>
      )
    case "cvet":
      return (
        <div className="flex items-center gap-1.5">
          <ColorSwatch hex={a.cvet_hex ?? swatchColor(a.cvet_color_code ?? "")} size={14} />
          <span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span>
          {a.cvet_nazvanie && <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>}
        </div>
      )
    case "status":
      return <StatusBadge statusId={a.status_id ?? 0} compact />
    case "wb_nom":
      return (
        <span className="font-mono text-[11px] text-stone-600 tabular-nums">
          {a.nomenklatura_wb ?? "—"}
        </span>
      )
    case "ozon_art":
      return (
        <span className="font-mono text-[11px] text-stone-600">{a.artikul_ozon ?? "—"}</span>
      )
    case "created":
      return <span className="text-xs text-stone-500">{relativeDate(a.created_at)}</span>
    case "updated":
      return <span className="text-xs text-stone-500">{relativeDate(a.updated_at)}</span>
    case "kategoriya":
      return <span className="text-xs text-stone-600">{a.kategoriya ?? "—"}</span>
    case "kollekciya":
      return <span className="text-xs text-stone-600">{a.kollekciya ?? "—"}</span>
    case "fabrika":
      return <span className="text-xs text-stone-600">{a.fabrika ?? "—"}</span>
    default:
      return null
  }
}

export function ArtikulyPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["artikuly-registry"],
    queryFn: fetchArtikulyRegistry,
    staleTime: 60 * 1000,
  })
  const { data: statusyData } = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })

  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
  const [columns, setColumns] = useState<string[]>(DEFAULT_COLUMNS)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkStatusOpen, setBulkStatusOpen] = useState(false)
  const bulkStatusRef = useRef<HTMLDivElement | null>(null)
  // W8.4 — drill-down overlay (клик по ячейке `artikul`).
  const [drillDown, setDrillDown] = useState<ArtikulRow | null>(null)
  // W1.5 — drag-resize колонок + persist через ui_preferences. Регистрируем все
  // возможные колонки (visibility управляется ColumnsManager-ом отдельно).
  const { widths: colWidths, bindResizer } = useResizableColumns(
    "artikuly",
    ARTIKULY_COLUMNS.map((c) => ({ id: c.key, defaultWidth: ARTIKULY_DEFAULT_WIDTHS[c.key] ?? 140 })),
  )

  // W8.1 — sort + ui_preferences persist (scope: "artikuly", key: "sort").
  const { sort, toggleSort, setSortState, sortRows } = useTableSort<ArtikulSortKey>()
  const sortLoadedRef = useRef(false)
  useEffect(() => {
    if (sortLoadedRef.current) return
    sortLoadedRef.current = true
    getUiPref<SortState<ArtikulSortKey>>("artikuly", "sort").then((v) => {
      if (v && v.column != null && v.direction != null) setSortState(v)
    }).catch(() => { /* ignore */ })
  }, [setSortState])
  useEffect(() => {
    if (!sortLoadedRef.current) return
    setUiPref("artikuly", "sort", sort).catch(() => { /* non-fatal */ })
  }, [sort])

  // W8.2 — pagination.
  const { page, setPage, pageSize, setPageSize, paginate, resetPage } = usePagination(50)

  // Все статусы tip='artikul' — для chips и bulk popover
  const artikulStatuses = useMemo(
    () => (statusyData ?? []).filter((s) => s.tip === "artikul"),
    [statusyData],
  )

  // Counts on chips
  const statusCounts = useMemo(() => {
    const acc: Record<number, number> = {}
    for (const a of data ?? []) {
      if (a.status_id != null) acc[a.status_id] = (acc[a.status_id] ?? 0) + 1
    }
    return acc
  }, [data])

  const filtered = useMemo<ArtikulRow[]>(() => {
    if (!data) return []
    let res = data
    if (statusFilter !== "all") {
      res = res.filter((a) => a.status_id === statusFilter)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter((a) => {
        return (
          a.artikul.toLowerCase().includes(q) ||
          (a.model_osnova_kod ?? "").toLowerCase().includes(q) ||
          (a.model_kod ?? "").toLowerCase().includes(q) ||
          (a.nazvanie_etiketka ?? "").toLowerCase().includes(q) ||
          (a.cvet_nazvanie ?? "").toLowerCase().includes(q) ||
          (a.color_en ?? "").toLowerCase().includes(q) ||
          (a.cvet_color_code ?? "").toLowerCase().includes(q) ||
          String(a.nomenklatura_wb ?? "").toLowerCase().includes(q) ||
          (a.artikul_ozon ?? "").toLowerCase().includes(q)
        )
      })
    }
    return res
  }, [data, statusFilter, search])

  // W8.1 — sort sits between filter and pagination.
  const sortedFiltered = useMemo<ArtikulRow[]>(
    () => sortRows(
      filtered as unknown as Record<string, unknown>[],
      (row, col) => getArtikulSortValue(row as unknown as ArtikulRow, col),
    ) as unknown as ArtikulRow[],
    [filtered, sortRows],
  )
  // Reset to page 1 when filters/sort change.
  useEffect(() => { resetPage() }, [search, statusFilter, sort.column, sort.direction, resetPage])
  const paginated = useMemo(() => paginate(sortedFiltered), [paginate, sortedFiltered])
  const visible = paginated.slice

  const toggleRow = useCallback((artikul: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(artikul)) next.delete(artikul)
      else next.add(artikul)
      return next
    })
  }, [])

  const toggleAll = useCallback(() => {
    setSelected((prev) => {
      const allKeys = visible.map((r) => r.artikul)
      const allSelected = allKeys.every((k) => prev.has(k))
      if (allSelected) {
        const next = new Set(prev)
        for (const k of allKeys) next.delete(k)
        return next
      }
      return new Set([...prev, ...allKeys])
    })
  }, [visible])

  // Resolve selected artikul strings → numeric ids (для bulk-update).
  const selectedIds = useMemo<number[]>(() => {
    if (!data || selected.size === 0) return []
    const ids: number[] = []
    for (const a of data) {
      if (selected.has(a.artikul)) ids.push(a.id)
    }
    return ids
  }, [data, selected])

  const handleBulkSetStatus = useCallback(async (statusId: number) => {
    if (selectedIds.length === 0) return
    try {
      await bulkUpdateArtikulStatus(selectedIds, statusId)
      await queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
      setSelected(new Set())
      setBulkStatusOpen(false)
    } catch (err) {
      window.alert(`Не удалось обновить статус: ${(err as Error).message}`)
    }
  }, [selectedIds, queryClient])

  // W7.3 — CSV-экспорт выбранных артикулов.  Используем `selected` (Set<artikul>)
  // → filter из data → renderable rows (только колонки, помеченные как видимые).
  const statusNameById = useMemo(() => {
    const m = new Map<number, string>()
    for (const s of statusyData ?? []) m.set(s.id, s.nazvanie)
    return m
  }, [statusyData])
  const handleBulkExport = useCallback(() => {
    if (!data || selected.size === 0) return
    const selectedRows = data
      .filter((a) => selected.has(a.artikul))
      .map((a) => ({
        artikul: a.artikul,
        model_osnova_kod: a.model_osnova_kod ?? "",
        model_kod: a.model_kod ?? "",
        nazvanie_etiketka: a.nazvanie_etiketka ?? "",
        cvet_color_code: a.cvet_color_code ?? "",
        cvet_nazvanie: a.cvet_nazvanie ?? "",
        color_en: a.color_en ?? "",
        status: a.status_id != null ? (statusNameById.get(a.status_id) ?? `#${a.status_id}`) : "",
        nomenklatura_wb: a.nomenklatura_wb ?? "",
        artikul_ozon: a.artikul_ozon ?? "",
        kategoriya: a.kategoriya ?? "",
        kollekciya: a.kollekciya ?? "",
        fabrika: a.fabrika ?? "",
        tovary_cnt: a.tovary_cnt,
        created_at: a.created_at ?? "",
        updated_at: a.updated_at ?? "",
      }))
    downloadCsv({
      filename: `artikuly-selected-${Date.now()}.csv`,
      rows: selectedRows,
      columns: [
        { key: "artikul", label: "Артикул" },
        { key: "model_osnova_kod", label: "Модель" },
        { key: "model_kod", label: "Вариация" },
        { key: "nazvanie_etiketka", label: "Название" },
        { key: "cvet_color_code", label: "Цвет (код)" },
        { key: "cvet_nazvanie", label: "Цвет (RU)" },
        { key: "color_en", label: "Цвет (EN)" },
        { key: "status", label: "Статус" },
        { key: "nomenklatura_wb", label: "WB номенкл." },
        { key: "artikul_ozon", label: "OZON артикул" },
        { key: "kategoriya", label: "Категория" },
        { key: "kollekciya", label: "Коллекция" },
        { key: "fabrika", label: "Производитель" },
        { key: "tovary_cnt", label: "SKU" },
        { key: "created_at", label: "Создан" },
        { key: "updated_at", label: "Обновлён" },
      ],
    })
  }, [data, selected, statusNameById])

  // Close popover on outside click / Escape.
  useEffect(() => {
    if (!bulkStatusOpen) return
    function onDocDown(e: MouseEvent) {
      if (!bulkStatusRef.current) return
      if (!bulkStatusRef.current.contains(e.target as Node)) setBulkStatusOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setBulkStatusOpen(false)
    }
    document.addEventListener("mousedown", onDocDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDocDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [bulkStatusOpen])

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка артикулов…</div>
  }
  if (error) {
    return <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки артикулов</div>
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
        <h1 className="text-3xl text-stone-900 cat-font-serif">Артикулы</h1>
        <div className="text-sm text-stone-500 mt-1">
          {data?.length ?? 0} артикулов
        </div>
      </div>

      {/* Filters bar */}
      <div className="px-6 pb-3 flex items-center gap-2 flex-wrap shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Артикул, модель, цвет, WB-ном., OZON…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-80"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
              aria-label="Очистить"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="h-5 w-px bg-stone-200 mx-1" />
        <span className="text-[10px] uppercase tracking-wider text-stone-400">Статус:</span>
        <button
          onClick={() => setStatusFilter("all")}
          className={`px-2 py-1 text-xs rounded-md transition-colors ${
            statusFilter === "all" ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          Все <span className="text-[10px] opacity-70 ml-1 tabular-nums">{data?.length ?? 0}</span>
        </button>
        {artikulStatuses.map((s) => (
          <button
            key={s.id}
            onClick={() => setStatusFilter(s.id)}
            className={`px-2 py-1 text-xs rounded-md transition-colors ${
              statusFilter === s.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {s.nazvanie}
            <span className="text-[10px] opacity-70 ml-1 tabular-nums">
              {statusCounts[s.id] ?? 0}
            </span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <div className="text-xs text-stone-500 tabular-nums">
            {filtered.length} из {data?.length ?? 0}
          </div>
          <ColumnsManager
            columns={ARTIKULY_COLUMNS}
            value={columns}
            onChange={setColumns}
            scope="artikuly"
            storageKey="columns"
          />
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 pb-3">
        <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 40 }} />
              {columns.map((key) => (
                <col key={key} style={{ width: `${colWidths[key] ?? ARTIKULY_DEFAULT_WIDTHS[key] ?? 140}px` }} />
              ))}
            </colgroup>
            <thead className="bg-stone-50/80 border-b border-stone-200 sticky top-0 z-10">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    className="rounded border-stone-300"
                    checked={
                      visible.length > 0 && visible.every((r) => selected.has(r.artikul))
                    }
                    onChange={toggleAll}
                  />
                </th>
                {columns.map((key) => {
                  const col = ARTIKULY_COLUMNS.find((c) => c.key === key)
                  const baseCls = "relative px-3 py-2.5 font-medium whitespace-nowrap"
                  if (ARTIKULY_SORTABLE.has(key)) {
                    const sortKey = key as ArtikulSortKey
                    return (
                      <SortableHeader
                        key={key}
                        active={sort.column === sortKey}
                        direction={sort.column === sortKey ? sort.direction : null}
                        onClick={() => toggleSort(sortKey)}
                        className={baseCls}
                      >
                        {col?.label}
                        <span {...bindResizer(key)} />
                      </SortableHeader>
                    )
                  }
                  return (
                    <th key={key} className={baseCls}>
                      {col?.label}
                      <span {...bindResizer(key)} />
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {visible.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60"
                >
                  <td className="px-3 py-2.5">
                    <input
                      type="checkbox"
                      className="rounded border-stone-300"
                      checked={selected.has(a.artikul)}
                      onChange={() => toggleRow(a.artikul)}
                    />
                  </td>
                  {columns.map((key) => (
                    <td key={key} className="px-3 py-2.5 whitespace-nowrap">
                      {key === "artikul" ? (
                        <button
                          type="button"
                          onClick={() => setDrillDown(a)}
                          className="font-mono text-xs text-stone-900 hover:text-stone-600 hover:underline underline-offset-2 cursor-pointer"
                          title="Открыть карточку артикула с SKU"
                        >
                          {a.artikul}
                        </button>
                      ) : key === "status" ? (
                        <InlineArtikulStatusCell
                          currentStatusId={a.status_id ?? null}
                          statusOptions={artikulStatuses}
                          onChange={async (newId) => {
                            await bulkUpdateArtikulStatus([a.id], newId)
                            await queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
                          }}
                        />
                      ) : renderCell(key, a)}
                    </td>
                  ))}
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

      {/* Bulk actions — кастомный бар, т.к. atomic BulkActionsBar не поддерживает
          submenu/popover. Стилистика — copy от matrix.tsx BulkBar. */}
      {selected.size > 0 && (
        <div
          className="border-t border-stone-200 bg-white px-6 py-3 flex items-center gap-3 shrink-0 shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.08)]"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="text-sm">
            Выбрано: <span className="font-medium tabular-nums">{selected.size}</span>
          </span>
          <div className="h-5 w-px bg-stone-200" />
          <div className="relative" ref={bulkStatusRef}>
            <button
              type="button"
              onClick={() => setBulkStatusOpen((v) => !v)}
              className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
            >
              Изменить статус
              <ChevronDown className="w-3 h-3" />
            </button>
            {bulkStatusOpen && (
              <div className="absolute bottom-9 left-0 z-50 w-48 bg-white border border-stone-200 rounded-md shadow-lg py-1">
                {artikulStatuses.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-stone-400 italic">Нет статусов</div>
                ) : (
                  artikulStatuses.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => handleBulkSetStatus(s.id)}
                      className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"
                    >
                      <StatusBadge
                        status={{ nazvanie: s.nazvanie, color: s.color }}
                        compact
                        size="sm"
                      />
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={handleBulkExport}
            className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Экспорт выбранных
          </button>
          <button
            type="button"
            onClick={() => { setSelected(new Set()); setBulkStatusOpen(false) }}
            className="ml-auto px-3 py-1 text-xs text-stone-500 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
          >
            <X className="w-3 h-3" /> Очистить
          </button>
        </div>
      )}

      {/* W8.4 — drill-down overlay по клику на ячейку артикула. */}
      {drillDown && (
        <ArtikulDrillDown
          row={drillDown}
          statusyData={statusyData}
          onClose={() => setDrillDown(null)}
        />
      )}
    </div>
  )
}
