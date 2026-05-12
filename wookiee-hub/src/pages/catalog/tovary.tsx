import React, { useMemo, useState, useCallback, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Search, X, Plus, Loader2 } from "lucide-react"
import {
  fetchTovaryRegistry, fetchStatusy, fetchSkleykiWb, fetchSkleykiOzon,
  bulkUpdateTovaryStatus, bulkLinkTovaryToSkleyka,
  getUiPref, setUiPref,
  type TovarRow, type TovarChannel, type SkleykaRow,
} from "@/lib/catalog/service"
import { supabase } from "@/lib/supabase"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { ColumnsManager, type ColumnDef } from "@/components/catalog/ui/columns-manager"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { SortableHeader } from "@/components/catalog/ui/sortable-header"
import { Pagination } from "@/components/catalog/ui/pagination"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { useResizableColumns } from "@/hooks/use-resizable-columns"
import { useTableSort, type SortState } from "@/hooks/use-table-sort"
import { usePagination } from "@/hooks/use-pagination"
import { downloadCsv } from "@/lib/catalog/csv-export"

// W1.5 — Default per-column widths (px) for the SKU registry (Товары) page.
// Keys must match TOVARY_COLUMNS[i].key.
const TOVARY_DEFAULT_WIDTHS: Record<string, number> = {
  barkod: 150,
  artikul: 150,
  model: 140,
  cvet: 160,
  razmer: 80,
  wb_nom: 130,
  ozon_art: 140,
  status_wb: 130,
  status_ozon: 130,
  status_sayt: 130,
  status_lamoda: 140,
  barkod_gs1: 140,
  barkod_gs2: 140,
  barkod_perehod: 150,
  cena_wb: 110,
  cena_ozon: 110,
  created: 110,
}

// 17 columns; all default-visible per Final Report MINOR fix.
const TOVARY_COLUMNS: ColumnDef[] = [
  { key: "barkod",          label: "Баркод",          default: true },
  { key: "artikul",         label: "Артикул",         default: true },
  { key: "model",           label: "Модель",          default: true },
  { key: "cvet",            label: "Цвет",            default: true },
  { key: "razmer",          label: "Размер",          default: true },
  { key: "wb_nom",          label: "WB-номенклатура", default: true },
  { key: "ozon_art",        label: "OZON-артикул",    default: true },
  { key: "status_wb",       label: "Статус WB",       default: true,  badge: "канал" },
  { key: "status_ozon",     label: "Статус OZON",     default: true,  badge: "канал" },
  { key: "status_sayt",     label: "Статус Сайт",     default: true,  badge: "канал" },
  { key: "status_lamoda",   label: "Статус Lamoda",   default: true,  badge: "канал" },
  { key: "barkod_gs1",      label: "Баркод GS1",      default: true },
  { key: "barkod_gs2",      label: "Баркод GS2",      default: true },
  { key: "barkod_perehod",  label: "Баркод перехода", default: true },
  { key: "cena_wb",         label: "Цена WB",         default: true },
  { key: "cena_ozon",       label: "Цена OZON",       default: true },
  { key: "created",         label: "Дата создания",   default: true },
]

const DEFAULT_COLUMNS = TOVARY_COLUMNS.filter((c) => c.default).map((c) => c.key)

type StatusGroupFilter = "all" | "active" | "archive" | "no-status"
type ChannelFilter = "all" | "wb" | "ozon" | "sayt" | "lamoda"
type GroupBy = "none" | "model" | "color" | "size" | "collection" | "channel"

// W8.1 — keys must match TOVARY_COLUMNS[i].key for sortable columns.
type TovarSortKey =
  | "barkod" | "artikul" | "model" | "cvet" | "razmer" | "wb_nom" | "ozon_art"
  | "status_wb" | "status_ozon" | "status_sayt" | "status_lamoda"
  | "barkod_gs1" | "barkod_gs2" | "barkod_perehod"
  | "cena_wb" | "cena_ozon" | "created"
const TOVARY_SORTABLE: ReadonlySet<string> = new Set<TovarSortKey>([
  "barkod", "artikul", "model", "cvet", "razmer", "wb_nom", "ozon_art",
  "status_wb", "status_ozon", "status_sayt", "status_lamoda",
  "barkod_gs1", "barkod_gs2", "barkod_perehod", "created",
])
function getTovarSortValue(t: TovarRow, col: TovarSortKey): unknown {
  switch (col) {
    case "barkod": return t.barkod
    case "artikul": return t.artikul ?? ""
    case "model": return t.model_osnova_kod ?? ""
    case "cvet": return t.cvet_color_code ?? ""
    case "razmer": return t.razmer ?? ""
    case "wb_nom": return t.nomenklatura_wb ?? null
    case "ozon_art": return t.artikul_ozon ?? ""
    case "status_wb": return t.status_id ?? null
    case "status_ozon": return t.status_ozon_id ?? null
    case "status_sayt": return t.status_sayt_id ?? null
    case "status_lamoda": return t.status_lamoda_id ?? null
    case "barkod_gs1": return t.barkod_gs1 ?? ""
    case "barkod_gs2": return t.barkod_gs2 ?? ""
    case "barkod_perehod": return t.barkod_perehod ?? ""
    case "cena_wb": return ""
    case "cena_ozon": return ""
    case "created": return t.created_at ?? ""
  }
}

// ─── Status badge popover ──────────────────────────────────────────────────

interface StatusOption {
  id: number
  nazvanie: string
  color: string | null
}

interface InlineStatusCellProps {
  /** Текущий статус — id или null. */
  currentStatusId: number | null
  /** Канал, по которому правим. */
  channel: TovarChannel
  /** Список статусов нужного `tip`. */
  options: StatusOption[]
  /** Применить новый статус (через service). */
  onChange: (statusId: number) => Promise<void>
}

function InlineStatusCell({
  currentStatusId, channel, options, onChange,
}: InlineStatusCellProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
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
        title={`Статус ${channel.toUpperCase()} — кликните чтобы изменить`}
      >
        {currentStatusId != null
          ? <StatusBadge statusId={currentStatusId} compact />
          : <span className="text-[11px] text-stone-400 italic px-1.5 py-px">—</span>}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-white border border-stone-200 rounded-lg shadow-lg z-30">
          <div className="p-2 border-b border-stone-100 flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-wider text-stone-400">
              Канал {channel.toUpperCase()}
            </div>
            {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin" />}
          </div>
          <div className="p-1 max-h-72 overflow-y-auto">
            {options.length === 0 && (
              <div className="px-2 py-3 text-xs text-stone-400 italic">Нет статусов</div>
            )}
            {options.map((s) => (
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

// ─── Cell rendering ───────────────────────────────────────────────────────

interface CellContext {
  statusOptions: {
    product: StatusOption[]
    sayt: StatusOption[]
    lamoda: StatusOption[]
  }
  onUpdateStatus: (
    barkod: string, statusId: number, channel: TovarChannel,
  ) => Promise<void>
}

function renderCell(
  key: string,
  t: TovarRow,
  ctx: CellContext,
): React.ReactNode {
  const onUpdate = (channel: TovarChannel) => async (statusId: number) => {
    await ctx.onUpdateStatus(t.barkod, statusId, channel)
  }
  switch (key) {
    case "barkod":
      return <span className="font-mono text-xs text-stone-700">{t.barkod}</span>
    case "artikul":
      return <span className="font-mono text-[11px] text-stone-600">{t.artikul ?? "—"}</span>
    case "model":
      return (
        <div className="flex flex-col">
          <span className="font-mono text-xs font-medium text-stone-900">
            {t.model_osnova_kod ?? "—"}
          </span>
          {t.nazvanie_etiketka && (
            <span className="text-[11px] text-stone-500">{t.nazvanie_etiketka}</span>
          )}
        </div>
      )
    case "cvet":
      return (
        <div className="flex items-center gap-1.5">
          <ColorSwatch hex={t.cvet_hex ?? swatchColor(t.cvet_color_code ?? "")} size={14} />
          <span className="font-mono text-xs text-stone-600">{t.cvet_color_code ?? "—"}</span>
          {t.cvet_ru && <span className="text-stone-500 text-[11px]">{t.cvet_ru}</span>}
        </div>
      )
    case "razmer":
      return <span className="font-mono text-xs">{t.razmer ?? "—"}</span>
    case "wb_nom":
      return (
        <span className="font-mono text-[11px] text-stone-500 tabular-nums">
          {t.nomenklatura_wb ?? "—"}
        </span>
      )
    case "ozon_art":
      return (
        <span className="font-mono text-[11px] text-stone-500">{t.artikul_ozon ?? "—"}</span>
      )
    case "status_wb":
      return (
        <InlineStatusCell
          currentStatusId={t.status_id ?? null}
          channel="wb"
          options={ctx.statusOptions.product}
          onChange={onUpdate("wb")}
        />
      )
    case "status_ozon":
      return (
        <InlineStatusCell
          currentStatusId={t.status_ozon_id ?? null}
          channel="ozon"
          options={ctx.statusOptions.product}
          onChange={onUpdate("ozon")}
        />
      )
    case "status_sayt":
      return (
        <InlineStatusCell
          currentStatusId={t.status_sayt_id ?? null}
          channel="sayt"
          options={ctx.statusOptions.sayt}
          onChange={onUpdate("sayt")}
        />
      )
    case "status_lamoda":
      return (
        <InlineStatusCell
          currentStatusId={t.status_lamoda_id ?? null}
          channel="lamoda"
          options={ctx.statusOptions.lamoda}
          onChange={onUpdate("lamoda")}
        />
      )
    case "barkod_gs1":
      return <span className="font-mono text-[11px] text-stone-500">{t.barkod_gs1 ?? "—"}</span>
    case "barkod_gs2":
      return <span className="font-mono text-[11px] text-stone-500">{t.barkod_gs2 ?? "—"}</span>
    case "barkod_perehod":
      return <span className="font-mono text-[11px] text-stone-500">{t.barkod_perehod ?? "—"}</span>
    case "cena_wb":
      return <span className="text-xs text-stone-400 italic">—</span>
    case "cena_ozon":
      return <span className="text-xs text-stone-400 italic">—</span>
    case "created":
      return <span className="text-xs text-stone-500">{relativeDate(t.created_at)}</span>
    default:
      return null
  }
}

// ─── Skleyka link modal ────────────────────────────────────────────────────

interface LinkSkleykaModalProps {
  channel: "wb" | "ozon"
  onClose: () => void
  onLink: (skleykaId: number) => Promise<void>
}

function LinkSkleykaModal({ channel, onClose, onLink }: LinkSkleykaModalProps) {
  const [search, setSearch] = useState("")
  const [creating, setCreating] = useState(false)
  const [linking, setLinking] = useState(false)
  const [newName, setNewName] = useState("")
  const queryClient = useQueryClient()

  const { data: skleyki, isLoading } = useQuery({
    queryKey: ["skleyki", channel],
    queryFn: () => (channel === "wb" ? fetchSkleykiWb() : fetchSkleykiOzon()),
    staleTime: 60 * 1000,
  })

  const filtered = useMemo<SkleykaRow[]>(() => {
    if (!skleyki) return []
    if (!search.trim()) return skleyki
    const q = search.trim().toLowerCase()
    return skleyki.filter((s) => s.nazvanie.toLowerCase().includes(q))
  }, [skleyki, search])

  const onSelect = useCallback(async (id: number) => {
    if (linking) return
    setLinking(true)
    try {
      await onLink(id)
    } finally {
      setLinking(false)
    }
  }, [linking, onLink])

  const onCreate = useCallback(async () => {
    if (!newName.trim() || creating) return
    setCreating(true)
    try {
      const table = channel === "wb" ? "skleyki_wb" : "skleyki_ozon"
      const { data: row, error } = await supabase
        .from(table)
        .insert({ nazvanie: newName.trim() })
        .select("id")
        .single()
      if (error) throw new Error(error.message)
      const id = (row as { id: number }).id
      await onLink(id)
      void queryClient.invalidateQueries({ queryKey: ["skleyki", channel] })
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`Не удалось создать склейку: ${(err as Error).message}`)
    } finally {
      setCreating(false)
    }
  }, [channel, creating, newName, onLink, queryClient])

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[85vh] flex flex-col">
        <div className="px-5 py-4 border-b border-stone-200 flex items-center justify-between shrink-0">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400">
              Канал {channel.toUpperCase()}
            </div>
            <div className="text-base font-medium text-stone-900">Привязать к склейке</div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-stone-100 rounded-md">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-3 border-b border-stone-100 shrink-0">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск склейки по названию…"
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="px-5 py-6 text-sm text-stone-400">Загрузка склеек…</div>
          )}
          {!isLoading && filtered.length === 0 && (
            <div className="px-5 py-6 text-sm text-stone-400 italic">
              {search ? "Ничего не найдено" : "Склеек пока нет"}
            </div>
          )}
          {filtered.map((s) => (
            <button
              key={s.id}
              type="button"
              disabled={linking}
              onClick={() => onSelect(s.id)}
              className="w-full px-5 py-2.5 text-left hover:bg-stone-50 border-b border-stone-100 last:border-0 disabled:opacity-50"
            >
              <div className="text-sm text-stone-900">{s.nazvanie}</div>
              {s.importer_nazvanie && (
                <div className="text-[11px] text-stone-500">{s.importer_nazvanie}</div>
              )}
            </button>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-stone-200 shrink-0 bg-stone-50/60">
          <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1.5">
            Создать новую
          </div>
          <div className="flex items-center gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Название склейки…"
              className="flex-1 px-3 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400 bg-white"
            />
            <button
              type="button"
              disabled={!newName.trim() || creating}
              onClick={onCreate}
              className="px-3 py-1.5 text-xs bg-stone-900 text-white rounded-md flex items-center gap-1.5 disabled:opacity-50 hover:bg-stone-800"
            >
              {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              Создать и привязать
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Composite search ──────────────────────────────────────────────────────

function matchesCompositeSearch(t: TovarRow, raw: string): boolean {
  if (!raw.trim()) return true
  const tokens = raw.split("/").map((s) => s.trim().toLowerCase()).filter(Boolean)
  if (tokens.length === 0) return true

  // Single token — flexible search across barkod/artikul/model/cvet
  if (tokens.length === 1) {
    const q = tokens[0]
    return (
      t.barkod.toLowerCase().includes(q) ||
      (t.artikul ?? "").toLowerCase().includes(q) ||
      (t.model_osnova_kod ?? "").toLowerCase().includes(q) ||
      (t.nazvanie_etiketka ?? "").toLowerCase().includes(q) ||
      (t.cvet_color_code ?? "").toLowerCase().includes(q) ||
      (t.cvet_ru ?? "").toLowerCase().includes(q) ||
      (t.color_en ?? "").toLowerCase().includes(q) ||
      (t.razmer_kod ?? "").toLowerCase().includes(q) ||
      String(t.nomenklatura_wb ?? "").toLowerCase().includes(q) ||
      (t.artikul_ozon ?? "").toLowerCase().includes(q)
    )
  }

  // Composite tokens: model / color / size — AND-логика
  const [modelTok, colorTok, sizeTok] = tokens

  if (modelTok) {
    const okModel =
      (t.model_osnova_kod ?? "").toLowerCase().includes(modelTok) ||
      (t.nazvanie_etiketka ?? "").toLowerCase().includes(modelTok)
    if (!okModel) return false
  }
  if (colorTok) {
    const okColor =
      (t.cvet_ru ?? "").toLowerCase().includes(colorTok) ||
      (t.color_en ?? "").toLowerCase().includes(colorTok) ||
      (t.cvet_color_code ?? "").toLowerCase().includes(colorTok)
    if (!okColor) return false
  }
  if (sizeTok) {
    const okSize = (t.razmer_kod ?? "").toLowerCase() === sizeTok
    if (!okSize) return false
  }
  return true
}

// ─── Status group filter ───────────────────────────────────────────────────

function isAllArchive(t: TovarRow, archiveIds: Set<number>): boolean {
  const ids = [t.status_id, t.status_ozon_id, t.status_sayt_id, t.status_lamoda_id].filter(
    (x): x is number => x != null,
  )
  if (ids.length === 0) return false
  return ids.every((id) => archiveIds.has(id))
}

function hasAnyStatus(t: TovarRow): boolean {
  return (
    t.status_id != null ||
    t.status_ozon_id != null ||
    t.status_sayt_id != null ||
    t.status_lamoda_id != null
  )
}

function applyStatusGroupFilter(
  rows: TovarRow[], filter: StatusGroupFilter, archiveIds: Set<number>,
): TovarRow[] {
  if (filter === "all") return rows
  if (filter === "archive") return rows.filter((t) => isAllArchive(t, archiveIds))
  if (filter === "no-status") return rows.filter((t) => !hasAnyStatus(t))
  // active = not all-archive AND has at least one status
  return rows.filter((t) => hasAnyStatus(t) && !isAllArchive(t, archiveIds))
}

function applyChannelFilter(rows: TovarRow[], channel: ChannelFilter): TovarRow[] {
  if (channel === "all") return rows
  const field: keyof TovarRow =
    channel === "wb" ? "status_id"
      : channel === "ozon" ? "status_ozon_id"
      : channel === "sayt" ? "status_sayt_id" : "status_lamoda_id"
  return rows.filter((t) => t[field] != null)
}

// ─── Group by ──────────────────────────────────────────────────────────────

interface Group {
  key: string
  label: string
  items: TovarRow[]
}

function groupRows(rows: TovarRow[], by: GroupBy): Group[] {
  if (by === "none") return [{ key: "_all", label: "", items: rows }]
  const map = new Map<string, TovarRow[]>()
  for (const t of rows) {
    let key: string
    switch (by) {
      case "model":
        key = t.model_osnova_kod ?? "—"
        break
      case "color":
        key = t.cvet_color_code ?? "—"
        break
      case "size":
        key = t.razmer_kod ?? "—"
        break
      case "collection":
        key = t.kollekciya ?? "—"
        break
      case "channel":
        if (t.status_id != null) key = "wb"
        else if (t.status_ozon_id != null) key = "ozon"
        else if (t.status_sayt_id != null) key = "sayt"
        else if (t.status_lamoda_id != null) key = "lamoda"
        else key = "no-channel"
        break
      default:
        key = "_all"
    }
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(t)
  }
  const labelFor = (key: string, items: TovarRow[]): string => {
    if (by === "model" && items[0]?.nazvanie_etiketka) {
      return `${key} · ${items[0].nazvanie_etiketka}`
    }
    if (by === "color" && items[0]?.cvet_ru) return `${key} · ${items[0].cvet_ru}`
    if (by === "channel") {
      return key === "wb" ? "WB"
        : key === "ozon" ? "OZON"
        : key === "sayt" ? "Сайт"
        : key === "lamoda" ? "Lamoda"
        : "Без канала"
    }
    return key
  }
  return Array.from(map.entries())
    .map(([key, items]) => ({ key, label: labelFor(key, items), items }))
    .sort((a, b) => a.key.localeCompare(b.key))
}

// ─── Page ──────────────────────────────────────────────────────────────────

export function TovaryPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["tovary-registry"],
    queryFn: fetchTovaryRegistry,
    staleTime: 60 * 1000,
  })
  const { data: statusyData } = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })

  const [search, setSearch] = useState("")
  const [statusGroup, setStatusGroup] = useState<StatusGroupFilter>("all")
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>("all")
  const [groupBy, setGroupBy] = useState<GroupBy>("none")
  const [columns, setColumns] = useState<string[]>(DEFAULT_COLUMNS)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [linkSkleykaChannel, setLinkSkleykaChannel] = useState<"wb" | "ozon" | null>(null)
  // W1.5 — drag-resize колонок + persist. Регистрируем все возможные колонки.
  const { widths: colWidths, bindResizer } = useResizableColumns(
    "tovary",
    TOVARY_COLUMNS.map((c) => ({ id: c.key, defaultWidth: TOVARY_DEFAULT_WIDTHS[c.key] ?? 130 })),
  )

  // W8.1 — sort + ui_preferences persist (scope: "tovary", key: "sort").
  const { sort, toggleSort, setSortState, sortRows } = useTableSort<TovarSortKey>()
  const sortLoadedRef = useRef(false)
  useEffect(() => {
    if (sortLoadedRef.current) return
    sortLoadedRef.current = true
    getUiPref<SortState<TovarSortKey>>("tovary", "sort").then((v) => {
      if (v && v.column != null && v.direction != null) setSortState(v)
    }).catch(() => { /* ignore */ })
  }, [setSortState])
  useEffect(() => {
    if (!sortLoadedRef.current) return
    setUiPref("tovary", "sort", sort).catch(() => { /* non-fatal */ })
  }, [sort])

  // W8.2 — pagination.
  const { page, setPage, pageSize, setPageSize, paginate, resetPage } = usePagination(50)

  const statusOptions = useMemo(() => {
    const all = statusyData ?? []
    const map = (tip: string): StatusOption[] =>
      all.filter((s) => s.tip === tip).map((s) => ({
        id: s.id, nazvanie: s.nazvanie, color: s.color,
      }))
    return {
      product: map("product"),
      sayt: map("sayt"),
      lamoda: map("lamoda"),
    }
  }, [statusyData])

  const archiveStatusIds = useMemo(() => {
    const ids = new Set<number>()
    for (const s of statusyData ?? []) {
      if (s.nazvanie === "Архив" || s.nazvanie === "Скрыт") ids.add(s.id)
    }
    return ids
  }, [statusyData])

  const updateStatusMutation = useMutation({
    mutationFn: async ({ barkod, statusId, channel }: {
      barkod: string; statusId: number; channel: TovarChannel
    }) => {
      await bulkUpdateTovaryStatus([barkod], statusId, channel)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tovary-registry"] })
    },
  })

  const onUpdateStatus = useCallback(
    async (barkod: string, statusId: number, channel: TovarChannel) => {
      await updateStatusMutation.mutateAsync({ barkod, statusId, channel })
    },
    [updateStatusMutation],
  )

  const filtered = useMemo<TovarRow[]>(() => {
    if (!data) return []
    let res: TovarRow[] = data
    res = applyChannelFilter(res, channelFilter)
    res = applyStatusGroupFilter(res, statusGroup, archiveStatusIds)
    if (search.trim()) {
      res = res.filter((t) => matchesCompositeSearch(t, search))
    }
    return res
  }, [data, channelFilter, statusGroup, archiveStatusIds, search])

  // W8.1 — sort after filter, before group.
  const sortedFiltered = useMemo<TovarRow[]>(
    () => sortRows(
      filtered as unknown as Record<string, unknown>[],
      (row, col) => getTovarSortValue(row as unknown as TovarRow, col),
    ) as unknown as TovarRow[],
    [filtered, sortRows],
  )
  const groups = useMemo(() => groupRows(sortedFiltered, groupBy), [sortedFiltered, groupBy])

  // W8.2 — pagination kicks in only when groupBy === "none"; when grouped, show
  // every item per group (cap removed — pagination across groups is non-obvious).
  useEffect(() => { resetPage() }, [search, statusGroup, channelFilter, groupBy, sort.column, sort.direction, resetPage])
  const paginated = useMemo(() => paginate(sortedFiltered), [paginate, sortedFiltered])
  const visibleByGroup = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "_all", label: "", items: sortedFiltered, visibleItems: paginated.slice }]
    }
    return groups.map((g) => ({ ...g, visibleItems: g.items }))
  }, [groupBy, groups, sortedFiltered, paginated.slice])

  const flatVisibleBarkods = useMemo(
    () => visibleByGroup.flatMap((g) => g.visibleItems.map((t) => t.barkod)),
    [visibleByGroup],
  )

  const toggleRow = useCallback((barkod: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(barkod)) next.delete(barkod)
      else next.add(barkod)
      return next
    })
  }, [])

  const toggleAll = useCallback(() => {
    setSelected((prev) => {
      const allSelected = flatVisibleBarkods.every((k) => prev.has(k))
      if (allSelected) {
        const next = new Set(prev)
        for (const k of flatVisibleBarkods) next.delete(k)
        return next
      }
      return new Set([...prev, ...flatVisibleBarkods])
    })
  }, [flatVisibleBarkods])

  const cellCtx: CellContext = useMemo(
    () => ({ statusOptions, onUpdateStatus }),
    [statusOptions, onUpdateStatus],
  )

  // W7.3 — CSV-экспорт выбранных SKU.  `selected` = Set<barkod>; берём строки
  // из data (не filtered — selection переживает фильтры/группы) и проецируем
  // в плоскую запись с человекочитаемыми колонками.
  const statusNameById = useMemo(() => {
    const m = new Map<number, string>()
    for (const s of statusyData ?? []) m.set(s.id, s.nazvanie)
    return m
  }, [statusyData])
  const handleBulkExport = useCallback(() => {
    if (!data || selected.size === 0) return
    const selectedRows = data
      .filter((t) => selected.has(t.barkod))
      .map((t) => ({
        barkod: t.barkod,
        artikul: t.artikul ?? "",
        model_osnova_kod: t.model_osnova_kod ?? "",
        nazvanie_etiketka: t.nazvanie_etiketka ?? "",
        cvet_color_code: t.cvet_color_code ?? "",
        cvet_ru: t.cvet_ru ?? "",
        razmer: t.razmer ?? "",
        nomenklatura_wb: t.nomenklatura_wb ?? "",
        artikul_ozon: t.artikul_ozon ?? "",
        status_wb: t.status_id != null ? (statusNameById.get(t.status_id) ?? `#${t.status_id}`) : "",
        status_ozon: t.status_ozon_id != null ? (statusNameById.get(t.status_ozon_id) ?? `#${t.status_ozon_id}`) : "",
        status_sayt: t.status_sayt_id != null ? (statusNameById.get(t.status_sayt_id) ?? `#${t.status_sayt_id}`) : "",
        status_lamoda: t.status_lamoda_id != null ? (statusNameById.get(t.status_lamoda_id) ?? `#${t.status_lamoda_id}`) : "",
        barkod_gs1: t.barkod_gs1 ?? "",
        barkod_gs2: t.barkod_gs2 ?? "",
        barkod_perehod: t.barkod_perehod ?? "",
        kategoriya: t.kategoriya ?? "",
        kollekciya: t.kollekciya ?? "",
        created_at: t.created_at ?? "",
      }))
    downloadCsv({
      filename: `tovary-selected-${Date.now()}.csv`,
      rows: selectedRows,
      columns: [
        { key: "barkod", label: "Баркод" },
        { key: "artikul", label: "Артикул" },
        { key: "model_osnova_kod", label: "Модель" },
        { key: "nazvanie_etiketka", label: "Название" },
        { key: "cvet_color_code", label: "Цвет (код)" },
        { key: "cvet_ru", label: "Цвет (RU)" },
        { key: "razmer", label: "Размер" },
        { key: "nomenklatura_wb", label: "WB номенкл." },
        { key: "artikul_ozon", label: "OZON артикул" },
        { key: "status_wb", label: "Статус WB" },
        { key: "status_ozon", label: "Статус OZON" },
        { key: "status_sayt", label: "Статус Сайт" },
        { key: "status_lamoda", label: "Статус Lamoda" },
        { key: "barkod_gs1", label: "Баркод GS1" },
        { key: "barkod_gs2", label: "Баркод GS2" },
        { key: "barkod_perehod", label: "Баркод перехода" },
        { key: "kategoriya", label: "Категория" },
        { key: "kollekciya", label: "Коллекция" },
        { key: "created_at", label: "Создан" },
      ],
    })
  }, [data, selected, statusNameById])

  const onLinkSkleyka = useCallback(async (skleykaId: number) => {
    if (!linkSkleykaChannel) return
    const barkods = Array.from(selected)
    if (barkods.length === 0) return
    try {
      await bulkLinkTovaryToSkleyka(barkods, skleykaId, linkSkleykaChannel)
      void queryClient.invalidateQueries({ queryKey: ["skleyki", linkSkleykaChannel] })
      setLinkSkleykaChannel(null)
      setSelected(new Set())
      // eslint-disable-next-line no-alert
      alert(`Привязано ${barkods.length} SKU к склейке.`)
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`Ошибка: ${(err as Error).message}`)
    }
  }, [linkSkleykaChannel, queryClient, selected])

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка SKU…</div>
  }
  if (error) {
    return <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки SKU</div>
  }

  const totalFiltered = filtered.length

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
        <h1 className="text-3xl text-stone-900 cat-font-serif">SKU / Товары</h1>
        <div className="text-sm text-stone-500 mt-1">
          {data?.length ?? 0} SKU
          {groupBy !== "none" && ` · ${groups.length} групп`}
        </div>
      </div>

      {/* Filter bar — row 1 */}
      <div className="px-6 pb-2 flex items-center gap-2 flex-wrap shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Audrey / черный / S — модель / цвет / размер"
            className="pl-8 pr-7 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-96"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="h-5 w-px bg-stone-200 mx-1" />
        <span className="text-[10px] uppercase tracking-wider text-stone-400">Канал:</span>
        {(["all", "wb", "ozon", "sayt", "lamoda"] as ChannelFilter[]).map((ch) => (
          <button
            key={ch}
            onClick={() => setChannelFilter(ch)}
            className={`px-2 py-1 text-xs rounded-md transition-colors ${
              channelFilter === ch ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {ch === "all" ? "Все"
              : ch === "wb" ? "WB"
              : ch === "ozon" ? "OZON"
              : ch === "sayt" ? "Сайт" : "Lamoda"}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-stone-400">Группировать:</span>
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupBy)}
            className="px-2 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none"
          >
            <option value="none">— Без группировки</option>
            <option value="model">По модели</option>
            <option value="color">По цвету</option>
            <option value="size">По размеру</option>
            <option value="collection">По коллекции</option>
            <option value="channel">По каналу</option>
          </select>
          <ColumnsManager
            columns={TOVARY_COLUMNS}
            value={columns}
            onChange={setColumns}
            scope="tovary"
            storageKey="columns"
          />
        </div>
      </div>

      {/* Filter bar — row 2: status group */}
      <div className="px-6 pb-3 flex items-center gap-2 flex-wrap shrink-0">
        <span className="text-[10px] uppercase tracking-wider text-stone-400">Статус:</span>
        {([
          { id: "all", label: "Все" },
          { id: "active", label: "Активные" },
          { id: "archive", label: "Архив" },
          { id: "no-status", label: "Без статуса" },
        ] as { id: StatusGroupFilter; label: string }[]).map((opt) => (
          <button
            key={opt.id}
            onClick={() => setStatusGroup(opt.id)}
            className={`px-2 py-1 text-xs rounded-md transition-colors ${
              statusGroup === opt.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {totalFiltered} из {data?.length ?? 0}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 pb-3">
        <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 40 }} />
              {columns.map((key) => (
                <col key={key} style={{ width: `${colWidths[key] ?? TOVARY_DEFAULT_WIDTHS[key] ?? 130}px` }} />
              ))}
            </colgroup>
            <thead className="bg-stone-50/80 border-b border-stone-200 sticky top-0 z-10">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    className="rounded border-stone-300"
                    checked={
                      flatVisibleBarkods.length > 0 &&
                      flatVisibleBarkods.every((k) => selected.has(k))
                    }
                    onChange={toggleAll}
                  />
                </th>
                {columns.map((key) => {
                  const col = TOVARY_COLUMNS.find((c) => c.key === key)
                  const baseCls = "relative px-3 py-2.5 font-medium whitespace-nowrap"
                  if (TOVARY_SORTABLE.has(key)) {
                    const sortKey = key as TovarSortKey
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
              {visibleByGroup.map((group) => (
                <React.Fragment key={group.key}>
                  {groupBy !== "none" && (
                    <tr className="bg-stone-50 border-b border-stone-200 sticky top-[36px] z-[1]">
                      <td colSpan={columns.length + 1} className="px-3 py-2">
                        <div className="flex items-baseline gap-2">
                          <h3 className="cat-font-serif italic text-base text-stone-800">
                            {group.label || "—"}
                          </h3>
                          <span className="text-[11px] text-stone-400 tabular-nums">
                            {group.items.length} SKU
                          </span>
                        </div>
                      </td>
                    </tr>
                  )}
                  {group.visibleItems.map((t) => (
                    <tr
                      key={t.id}
                      className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60"
                    >
                      <td className="px-3 py-2.5">
                        <input
                          type="checkbox"
                          className="rounded border-stone-300"
                          checked={selected.has(t.barkod)}
                          onChange={() => toggleRow(t.barkod)}
                        />
                      </td>
                      {columns.map((key) => (
                        <td key={key} className="px-3 py-2.5 whitespace-nowrap">
                          {renderCell(key, t, cellCtx)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
          {groupBy === "none" ? (
            <Pagination
              page={paginated.page}
              totalPages={paginated.totalPages}
              total={paginated.total}
              pageSize={paginated.pageSize}
              onPage={setPage}
              onPageSize={(s) => { setPageSize(s); resetPage() }}
            />
          ) : (
            <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
              Всего: {totalFiltered}. Пагинация недоступна с группировкой — выключите группировку для постраничного просмотра.
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
            id: "link-wb",
            label: "Привязать к склейке (WB)",
            onClick: () => setLinkSkleykaChannel("wb"),
          },
          {
            id: "link-ozon",
            label: "Привязать к склейке (OZON)",
            onClick: () => setLinkSkleykaChannel("ozon"),
          },
          {
            id: "export",
            label: "Экспорт выбранных",
            onClick: handleBulkExport,
          },
        ]}
      />

      {/* Modals */}
      {linkSkleykaChannel && (
        <LinkSkleykaModal
          channel={linkSkleykaChannel}
          onClose={() => setLinkSkleykaChannel(null)}
          onLink={onLinkSkleyka}
        />
      )}
    </div>
  )
}
