import { useMemo, useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search, X } from "lucide-react"
import {
  fetchArtikulyRegistry, fetchStatusy,
  type ArtikulRow,
} from "@/lib/catalog/service"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { ColumnsManager, type ColumnDef } from "@/components/catalog/ui/columns-manager"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { useSearchParams } from "react-router-dom"

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
  const [, setSearchParams] = useSearchParams()

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

  const visible = filtered.slice(0, 200)

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
          <table className="w-full text-sm">
            <thead className="bg-stone-50/80 border-b border-stone-200 sticky top-0 z-10">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="w-10 px-3 py-2.5">
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
                  return (
                    <th key={key} className="px-3 py-2.5 font-medium whitespace-nowrap">
                      {col?.label}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {visible.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 cursor-pointer"
                  onClick={() => setSearchParams({ artikul: a.artikul })}
                >
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="rounded border-stone-300"
                      checked={selected.has(a.artikul)}
                      onChange={() => toggleRow(a.artikul)}
                    />
                  </td>
                  {columns.map((key) => (
                    <td key={key} className="px-3 py-2.5 whitespace-nowrap">
                      {renderCell(key, a)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length > visible.length && (
            <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
              Показаны первые {visible.length} из {filtered.length}.
            </div>
          )}
        </div>
      </div>

      {/* Bulk actions */}
      <BulkActionsBar
        selectedCount={selected.size}
        onClear={() => setSelected(new Set())}
        actions={[
          {
            id: "change-status",
            label: "Изменить статус",
            onClick: () => alert("TODO Wave 3: модалка bulk-change status (artikul)"),
          },
          {
            id: "export",
            label: "Экспорт выбранных",
            onClick: () => alert("TODO: экспорт CSV/XLSX выбранных артикулов"),
          },
        ]}
      />
    </div>
  )
}
