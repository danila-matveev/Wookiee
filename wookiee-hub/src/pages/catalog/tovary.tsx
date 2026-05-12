import React, { useMemo, useState, useCallback, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Search, X, Plus, Loader2, ChevronDown, ChevronRight } from "lucide-react"
import {
  fetchTovaryRegistry, fetchStatusy, fetchSkleykiWb, fetchSkleykiOzon,
  bulkUpdateTovaryStatus, bulkLinkTovaryToSkleyka,
  getUiPref, setUiPref,
  type TovarRow, type TovarChannel, type SkleykaRow,
} from "@/lib/catalog/service"
import { supabase } from "@/lib/supabase"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { ColumnsManager } from "@/components/catalog/ui/columns-manager"
import { useColumnConfig } from "@/hooks/use-column-config"
import { TOVARY_COLUMNS_FULL } from "@/lib/catalog/column-catalogs"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { SortableHeader } from "@/components/catalog/ui/sortable-header"
import { Pagination } from "@/components/catalog/ui/pagination"
import { FilterBar } from "@/components/catalog/ui/filter-bar"
import { CellText } from "@/components/catalog/ui/cell-text"
import { swatchColor, relativeDate } from "@/lib/catalog/color-utils"
import { useResizableColumns } from "@/hooks/use-resizable-columns"
import { useTableSort, type SortState } from "@/hooks/use-table-sort"
import { usePagination } from "@/hooks/use-pagination"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useCollapsibleGroups } from "@/hooks/use-collapsible-groups"
import { downloadCsv } from "@/lib/catalog/csv-export"
import { translateError } from "@/lib/catalog/error-translator"

// W1.5 — Default per-column widths (px) for the SKU registry (Товары) page.
// W9.5 — расширено новыми ключами из TOVARY_COLUMNS_FULL (column-catalogs).
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
  // W9.5
  sku_china_size: 130,
  ozon_product_id: 150,
  ozon_fbo_sku_id: 150,
  lamoda_seller_sku: 160,
  kollekciya: 140,
  kategoriya: 130,
}

// W9.9 — синтетический ключ колонки «Статус» (для одного выбранного канала).
// В TOVARY_COLUMNS не включаем — он подставляется в effectiveColumns динамически
// и заменяет 4 раздельные колонки status_<channel> когда выбран конкретный канал.
const STATUS_CHANNEL_KEY = "status_channel"
const CHANNEL_STATUS_KEYS = ["status_wb", "status_ozon", "status_sayt", "status_lamoda"] as const

// W9.5 — каталог колонок переехал в shared `lib/catalog/column-catalogs.ts`.
// Алиас оставлен для backward-compat локального кода (`labelForColumn` ниже).
const TOVARY_COLUMNS = TOVARY_COLUMNS_FULL

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
  /**
   * W9.2 — резолвер id→{nazvanie,color} из живых `statusy` БД.
   * Нужен, потому что `<StatusBadge statusId={…}>` использует
   * хардкод CATALOG_STATUSES (id 1-7) и возвращает `null` для
   * любых остальных id, отчего status-колонки выглядели пустыми.
   */
  resolveStatus: (statusId: number) => { nazvanie: string; color: string | null } | null
}

function InlineStatusCell({
  currentStatusId, channel, options, onChange, resolveStatus,
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
      alert(translateError(err))
    } finally {
      setSaving(false)
    }
  }, [onChange, saving])

  // W9.2 — рендер бейджа: сначала пытаемся резолвить через живой справочник
  // statusy (любой id из БД), при отсутствии — fallback на нумерованный значок,
  // чтобы колонка всё равно содержала видимый контент.
  const resolved = currentStatusId != null ? resolveStatus(currentStatusId) : null

  return (
    <div className="relative inline-block" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="hover:ring-1 hover:ring-stone-400 rounded-md transition-all"
        title={`Статус ${channel.toUpperCase()} — кликните чтобы изменить`}
      >
        {currentStatusId != null && resolved ? (
          <StatusBadge
            status={{ nazvanie: resolved.nazvanie, color: resolved.color ?? "gray" }}
            compact
          />
        ) : currentStatusId != null ? (
          <span className="px-1.5 py-px text-[11px] rounded-md ring-1 ring-inset bg-stone-100 text-stone-600 ring-stone-500/20 font-mono">
            #{currentStatusId}
          </span>
        ) : (
          <span className="text-[11px] text-stone-400 italic px-1.5 py-px">—</span>
        )}
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
  /** W9.2 — резолв любого статус-id через live `statusy`. */
  resolveStatus: (statusId: number) => { nazvanie: string; color: string | null } | null
  onUpdateStatus: (
    barkod: string, statusId: number, channel: TovarChannel,
  ) => Promise<void>
  /** W9.9 — для синтетической колонки «Статус» (один выбранный канал). */
  selectedChannel?: TovarChannel
}

function renderChannelStatusCell(t: TovarRow, ctx: CellContext): React.ReactNode {
  const ch = ctx.selectedChannel
  if (!ch) return null
  const onChange = async (id: number) => { await ctx.onUpdateStatus(t.barkod, id, ch) }
  const currentId =
    ch === "wb" ? t.status_id
      : ch === "ozon" ? t.status_ozon_id
      : ch === "sayt" ? t.status_sayt_id
      : t.status_lamoda_id
  const options =
    ch === "sayt" ? ctx.statusOptions.sayt
      : ch === "lamoda" ? ctx.statusOptions.lamoda
      : ctx.statusOptions.product
  return (
    <InlineStatusCell
      currentStatusId={currentId ?? null}
      channel={ch}
      options={options}
      onChange={onChange}
      resolveStatus={ctx.resolveStatus}
    />
  )
}

function renderCell(
  key: string,
  t: TovarRow,
  ctx: CellContext,
): React.ReactNode {
  const onUpdate = (channel: TovarChannel) => async (statusId: number) => {
    await ctx.onUpdateStatus(t.barkod, statusId, channel)
  }
  if (key === STATUS_CHANNEL_KEY) return renderChannelStatusCell(t, ctx)
  switch (key) {
    case "barkod":
      return <CellText className="font-mono text-xs text-stone-700" title={t.barkod}>{t.barkod}</CellText>
    case "artikul":
      return <CellText className="font-mono text-[11px] text-stone-600" title={t.artikul ?? ""}>{t.artikul ?? "—"}</CellText>
    case "model":
      return (
        <div className="flex flex-col min-w-0">
          <CellText className="font-mono text-xs font-medium text-stone-900" title={t.model_osnova_kod ?? ""}>
            {t.model_osnova_kod ?? "—"}
          </CellText>
          {t.nazvanie_etiketka && (
            <CellText className="text-[11px] text-stone-500" title={t.nazvanie_etiketka}>{t.nazvanie_etiketka}</CellText>
          )}
        </div>
      )
    case "cvet":
      return (
        <div className="flex items-center gap-1.5 min-w-0">
          <ColorSwatch hex={t.cvet_hex ?? swatchColor(t.cvet_color_code ?? "")} size={14} />
          <CellText className="font-mono text-xs text-stone-600" title={t.cvet_color_code ?? ""}>{t.cvet_color_code ?? "—"}</CellText>
          {t.cvet_ru && <CellText className="text-stone-500 text-[11px]" title={t.cvet_ru}>{t.cvet_ru}</CellText>}
        </div>
      )
    case "razmer":
      return <CellText className="font-mono text-xs" title={t.razmer ?? ""}>{t.razmer ?? "—"}</CellText>
    case "wb_nom":
      return (
        <CellText className="font-mono text-[11px] text-stone-500 tabular-nums" title={t.nomenklatura_wb != null ? String(t.nomenklatura_wb) : ""}>
          {t.nomenklatura_wb ?? "—"}
        </CellText>
      )
    case "ozon_art":
      return (
        <CellText className="font-mono text-[11px] text-stone-500" title={t.artikul_ozon ?? ""}>{t.artikul_ozon ?? "—"}</CellText>
      )
    case "status_wb":
      return (
        <InlineStatusCell
          currentStatusId={t.status_id ?? null}
          channel="wb"
          options={ctx.statusOptions.product}
          onChange={onUpdate("wb")}
          resolveStatus={ctx.resolveStatus}
        />
      )
    case "status_ozon":
      return (
        <InlineStatusCell
          currentStatusId={t.status_ozon_id ?? null}
          channel="ozon"
          options={ctx.statusOptions.product}
          onChange={onUpdate("ozon")}
          resolveStatus={ctx.resolveStatus}
        />
      )
    case "status_sayt":
      return (
        <InlineStatusCell
          currentStatusId={t.status_sayt_id ?? null}
          channel="sayt"
          options={ctx.statusOptions.sayt}
          onChange={onUpdate("sayt")}
          resolveStatus={ctx.resolveStatus}
        />
      )
    case "status_lamoda":
      return (
        <InlineStatusCell
          currentStatusId={t.status_lamoda_id ?? null}
          channel="lamoda"
          options={ctx.statusOptions.lamoda}
          onChange={onUpdate("lamoda")}
          resolveStatus={ctx.resolveStatus}
        />
      )
    case "barkod_gs1":
      return <CellText className="font-mono text-[11px] text-stone-500" title={t.barkod_gs1 ?? ""}>{t.barkod_gs1 ?? "—"}</CellText>
    case "barkod_gs2":
      return <CellText className="font-mono text-[11px] text-stone-500" title={t.barkod_gs2 ?? ""}>{t.barkod_gs2 ?? "—"}</CellText>
    case "barkod_perehod":
      return <CellText className="font-mono text-[11px] text-stone-500" title={t.barkod_perehod ?? ""}>{t.barkod_perehod ?? "—"}</CellText>
    case "cena_wb":
      return <span className="text-xs text-stone-400 italic">—</span>
    case "cena_ozon":
      return <span className="text-xs text-stone-400 italic">—</span>
    case "created":
      return <CellText className="text-xs text-stone-500" title={t.created_at ?? ""}>{relativeDate(t.created_at)}</CellText>
    // W9.5 — расширения для нового конфигуратора (скрыты по умолчанию).
    case "sku_china_size":
      return <CellText className="font-mono text-[11px] text-stone-500" title={t.sku_china_size ?? ""}>{t.sku_china_size ?? "—"}</CellText>
    case "ozon_product_id":
      return <CellText className="font-mono text-[11px] text-stone-500 tabular-nums" title={t.ozon_product_id != null ? String(t.ozon_product_id) : ""}>{t.ozon_product_id ?? "—"}</CellText>
    case "ozon_fbo_sku_id":
      return <CellText className="font-mono text-[11px] text-stone-500 tabular-nums" title={t.ozon_fbo_sku_id != null ? String(t.ozon_fbo_sku_id) : ""}>{t.ozon_fbo_sku_id ?? "—"}</CellText>
    case "lamoda_seller_sku":
      return <CellText className="font-mono text-[11px] text-stone-500" title={t.lamoda_seller_sku ?? ""}>{t.lamoda_seller_sku ?? "—"}</CellText>
    case "kollekciya":
      return <CellText className="text-xs text-stone-600" title={t.kollekciya ?? ""}>{t.kollekciya ?? "—"}</CellText>
    case "kategoriya":
      return <CellText className="text-xs text-stone-600" title={t.kategoriya ?? ""}>{t.kategoriya ?? "—"}</CellText>
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
      alert(translateError(err))
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

// W9.3 — все строковые поля SKU, релевантные для поиска (lowercase).
function tovarSearchFields(t: TovarRow): string[] {
  return [
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
    t.sku_china_size,
    t.lamoda_seller_sku,
    t.nomenklatura_wb != null ? String(t.nomenklatura_wb) : null,
    t.ozon_product_id != null ? String(t.ozon_product_id) : null,
    t.ozon_fbo_sku_id != null ? String(t.ozon_fbo_sku_id) : null,
  ]
    .filter((v): v is string => typeof v === "string" && v.length > 0)
    .map((v) => v.toLowerCase())
}

function matchesCompositeSearch(t: TovarRow, raw: string): boolean {
  if (!raw.trim()) return true
  const tokens = raw.split("/").map((s) => s.trim().toLowerCase()).filter(Boolean)
  if (tokens.length === 0) return true

  const fields = tovarSearchFields(t)

  // Single token — flexible OR-search по всем полям SKU.
  if (tokens.length === 1) {
    const q = tokens[0]
    return fields.some((f) => f.includes(q))
  }

  // Composite tokens (model/color/size) — каждый токен должен
  // совпасть хотя бы с одним полем (AND между токенами, OR по полям).
  // Регистр-инвариантно. Это покрывает запросы вроде `Lucky/black`,
  // `Lucky/чёрный`, `Audrey/red/S`.
  return tokens.every((tok) => fields.some((f) => f.includes(tok)))
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

// W9.9 — статусы продукта на канале, означающие «ещё не выведен в продажу»
// (pre-launch). SKU с таким статусом по каналу не считается продаваемым на нём.
// Все остальные статусы (Продаётся / Выводим / Архив / Запуск / Скрыт) — это
// «канал засветился»: active или blocked, но факт продажи был. Это совпадает
// с поведением WB-кабинета: архивные карточки видны.
const PRE_LAUNCH_STATUS_NAMES: ReadonlySet<string> = new Set([
  "План", "Подготовка", "Планирование",
])

interface StatusLookup {
  isPreLaunch: (statusId: number | null | undefined) => boolean
}

function channelStatusField(channel: Exclude<ChannelFilter, "all">): keyof TovarRow {
  return channel === "wb" ? "status_id"
    : channel === "ozon" ? "status_ozon_id"
    : channel === "sayt" ? "status_sayt_id" : "status_lamoda_id"
}

function applyChannelFilter(
  rows: TovarRow[], channel: ChannelFilter, lookup: StatusLookup,
): TovarRow[] {
  if (channel === "all") return rows
  const field = channelStatusField(channel)
  return rows.filter((t) => {
    const id = t[field] as number | null | undefined
    if (id == null) return false
    // active + blocked включаем, pre-launch (План/Подготовка) — исключаем.
    return !lookup.isPreLaunch(id)
  })
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
  // W9.3 — debounce 300мс. tovary-реестр обычно >5k строк; на каждом keystroke
  // полный scan + render даёт jank, debounce делает поиск отзывчивым.
  const debouncedSearch = useDebouncedValue(search, 300)
  const [statusGroup, setStatusGroup] = useState<StatusGroupFilter>("all")
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>("all")
  // W9.4 — multi-select chip-фильтры (модель, цвет, размер, статус по каналам).
  const [selectedModelKods, setSelectedModelKods] = useState<Set<string>>(new Set())
  const [selectedColorCodes, setSelectedColorCodes] = useState<Set<string>>(new Set())
  const [selectedRazmery, setSelectedRazmery] = useState<Set<string>>(new Set())
  const [selectedChannelStatusIds, setSelectedChannelStatusIds] = useState<Set<number>>(new Set())
  const [groupBy, setGroupBy] = useState<GroupBy>("none")
  // W9.6 — Notion-style collapsible group headers.
  const { isCollapsed: isGroupCollapsed, toggle: toggleGroupCollapsed } = useCollapsibleGroups("tovary")
  // W9.5 — конфигуратор колонок (видимость + порядок + сброс) через единый хук.
  const columnConfig = useColumnConfig("tovary", TOVARY_COLUMNS)
  const columns = columnConfig.visibleColumns
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

  // W9.4 — опции для компактного FilterBar (модель, цвет, размер, статус).
  const modelOptions = useMemo(() => {
    const acc = new Map<string, { label: string; count: number }>()
    for (const t of data ?? []) {
      const kod = t.model_osnova_kod
      if (!kod) continue
      const label = t.nazvanie_etiketka ? `${kod} · ${t.nazvanie_etiketka}` : kod
      const prev = acc.get(kod)
      acc.set(kod, { label, count: (prev?.count ?? 0) + 1 })
    }
    return Array.from(acc.entries())
      .sort(([a], [b]) => a.localeCompare(b, "ru"))
      .map(([value, info]) => ({ value, label: info.label, count: info.count }))
  }, [data])
  const colorOptions = useMemo(() => {
    const acc = new Map<string, { label: string; count: number }>()
    for (const t of data ?? []) {
      const code = t.cvet_color_code
      if (!code) continue
      const label = t.cvet_ru ? `${code} · ${t.cvet_ru}` : code
      const prev = acc.get(code)
      acc.set(code, { label, count: (prev?.count ?? 0) + 1 })
    }
    return Array.from(acc.entries())
      .sort(([a], [b]) => a.localeCompare(b, "ru"))
      .map(([value, info]) => ({ value, label: info.label, count: info.count }))
  }, [data])
  const razmerOptions = useMemo(() => {
    const acc = new Map<string, number>()
    for (const t of data ?? []) {
      const r = t.razmer_kod
      if (!r) continue
      acc.set(r, (acc.get(r) ?? 0) + 1)
    }
    return Array.from(acc.entries())
      .sort(([a], [b]) => a.localeCompare(b, "ru", { numeric: true }))
      .map(([value, count]) => ({ value, label: value, count }))
  }, [data])
  // Статусы для multi-select — берём «product» (основной канал WB) +
  // дополняем sayt/lamoda, чтобы chip покрывал все каналы. Дедупликация по id.
  const channelStatusOptions = useMemo(() => {
    const seen = new Map<number, { nazvanie: string; count: number }>()
    for (const s of statusyData ?? []) {
      if (s.tip === "product" || s.tip === "sayt" || s.tip === "lamoda") {
        if (!seen.has(s.id)) seen.set(s.id, { nazvanie: s.nazvanie, count: 0 })
      }
    }
    for (const t of data ?? []) {
      for (const id of [t.status_id, t.status_ozon_id, t.status_sayt_id, t.status_lamoda_id]) {
        if (id != null && seen.has(id)) {
          seen.get(id)!.count += 1
        }
      }
    }
    return Array.from(seen.entries())
      .sort(([, a], [, b]) => a.nazvanie.localeCompare(b.nazvanie, "ru"))
      .map(([id, info]) => ({ value: String(id), label: info.nazvanie, count: info.count }))
  }, [statusyData, data])

  const archiveStatusIds = useMemo(() => {
    const ids = new Set<number>()
    for (const s of statusyData ?? []) {
      if (s.nazvanie === "Архив" || s.nazvanie === "Скрыт") ids.add(s.id)
    }
    return ids
  }, [statusyData])

  // W9.2 — резолвер id→{nazvanie,color} по всем статусам из БД,
  // вне зависимости от tip (product/sayt/lamoda/artikul/model/…).
  const statusById = useMemo(() => {
    const m = new Map<number, { nazvanie: string; color: string | null }>()
    for (const s of statusyData ?? []) {
      m.set(s.id, { nazvanie: s.nazvanie, color: s.color })
    }
    return m
  }, [statusyData])
  const resolveStatus = useCallback(
    (id: number) => statusById.get(id) ?? null,
    [statusById],
  )

  // W9.9 — pre-launch статусы: SKU с таким статусом по каналу считаем «ещё не
  // в продаже» и отфильтровываем при выборе конкретного канала.
  const preLaunchStatusIds = useMemo(() => {
    const ids = new Set<number>()
    for (const s of statusyData ?? []) {
      if (PRE_LAUNCH_STATUS_NAMES.has(s.nazvanie)) ids.add(s.id)
    }
    return ids
  }, [statusyData])

  const statusLookup = useMemo<StatusLookup>(
    () => ({ isPreLaunch: (id) => id != null && preLaunchStatusIds.has(id) }),
    [preLaunchStatusIds],
  )

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
    res = applyChannelFilter(res, channelFilter, statusLookup)
    res = applyStatusGroupFilter(res, statusGroup, archiveStatusIds)
    if (selectedModelKods.size > 0) {
      res = res.filter((t) => t.model_osnova_kod != null && selectedModelKods.has(t.model_osnova_kod))
    }
    if (selectedColorCodes.size > 0) {
      res = res.filter((t) => t.cvet_color_code != null && selectedColorCodes.has(t.cvet_color_code))
    }
    if (selectedRazmery.size > 0) {
      res = res.filter((t) => t.razmer_kod != null && selectedRazmery.has(t.razmer_kod))
    }
    if (selectedChannelStatusIds.size > 0) {
      // W9.4 — статус по каналам: матчим, если хотя бы один из 4 каналов содержит
      // выбранный статус. Так чип «Статус» работает как multi-OR через все каналы.
      res = res.filter((t) => {
        const ids = [t.status_id, t.status_ozon_id, t.status_sayt_id, t.status_lamoda_id]
        return ids.some((id) => id != null && selectedChannelStatusIds.has(id))
      })
    }
    if (debouncedSearch.trim()) {
      res = res.filter((t) => matchesCompositeSearch(t, debouncedSearch))
    }
    return res
  }, [
    data, channelFilter, statusLookup, statusGroup, archiveStatusIds,
    selectedModelKods, selectedColorCodes, selectedRazmery, selectedChannelStatusIds,
    debouncedSearch,
  ])

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
  useEffect(() => {
    resetPage()
  }, [
    debouncedSearch, statusGroup, channelFilter, groupBy, sort.column, sort.direction,
    selectedModelKods, selectedColorCodes, selectedRazmery, selectedChannelStatusIds,
    resetPage,
  ])
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

  // W9.9 — когда выбран один канал, прячем 4 колонки status_<channel> и
  // показываем одну колонку «Статус» (status_channel) на месте первой из них.
  const selectedChannel: TovarChannel | undefined = useMemo(
    () => (channelFilter === "all" ? undefined : channelFilter),
    [channelFilter],
  )

  const cellCtx: CellContext = useMemo(
    () => ({ statusOptions, resolveStatus, onUpdateStatus, selectedChannel }),
    [statusOptions, resolveStatus, onUpdateStatus, selectedChannel],
  )

  // Список ключей колонок, фактически отрисованных в таблице (учитывает фильтр канала).
  const effectiveColumns = useMemo<string[]>(() => {
    if (!selectedChannel) return columns
    const result: string[] = []
    let inserted = false
    for (const key of columns) {
      if ((CHANNEL_STATUS_KEYS as readonly string[]).includes(key)) {
        if (!inserted) {
          result.push(STATUS_CHANNEL_KEY)
          inserted = true
        }
        continue
      }
      result.push(key)
    }
    // Если у пользователя были скрыты все channel-status колонки — всё равно
    // вставим status_channel перед barkod_gs1, чтобы статус был виден.
    if (!inserted) {
      const anchorIdx = result.findIndex((k) => k === "barkod_gs1")
      if (anchorIdx >= 0) result.splice(anchorIdx, 0, STATUS_CHANNEL_KEY)
      else result.push(STATUS_CHANNEL_KEY)
    }
    return result
  }, [columns, selectedChannel])

  const channelLabel = (ch: TovarChannel): string =>
    ch === "wb" ? "WB" : ch === "ozon" ? "OZON" : ch === "sayt" ? "Сайт" : "Lamoda"

  const labelForColumn = useCallback((key: string): string => {
    if (key === STATUS_CHANNEL_KEY && selectedChannel) {
      return `Статус ${channelLabel(selectedChannel)}`
    }
    return TOVARY_COLUMNS.find((c) => c.key === key)?.label ?? key
  }, [selectedChannel])

  // Ширина для status_channel — берём из соответствующей канальной колонки.
  const widthForColumn = useCallback((key: string): number => {
    if (key === STATUS_CHANNEL_KEY && selectedChannel) {
      const srcKey = `status_${selectedChannel}` as keyof typeof TOVARY_DEFAULT_WIDTHS
      return colWidths[srcKey] ?? TOVARY_DEFAULT_WIDTHS[srcKey] ?? 130
    }
    return colWidths[key] ?? TOVARY_DEFAULT_WIDTHS[key] ?? 130
  }, [colWidths, selectedChannel])

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
      alert(translateError(err))
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
            placeholder="Audrey / black / S — поиск по баркоду, модели, цвету, размеру"
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

      {/* W9.4 — Filter bar — row 1.5: компактные dropdown-фильтры
          (модель, цвет, размер, статус по каналам).
          TODO(W9.4): добавить chip «Бренд» — нужно протащить brand_id/brand
          через `fetchTovaryRegistry` (modeli_osnova.brand_id), сейчас оно не
          выбирается. */}
      <div className="px-6 pb-2 shrink-0">
        <FilterBar
          filters={[
            { key: "model", label: "Модель", options: modelOptions },
            { key: "cvet", label: "Цвет", options: colorOptions },
            { key: "razmer", label: "Размер", options: razmerOptions },
            { key: "status", label: "Статус по каналам", options: channelStatusOptions },
          ]}
          values={{
            model: Array.from(selectedModelKods),
            cvet: Array.from(selectedColorCodes),
            razmer: Array.from(selectedRazmery),
            status: Array.from(selectedChannelStatusIds).map(String),
          }}
          onChange={(key, next) => {
            if (key === "model") setSelectedModelKods(new Set(next))
            else if (key === "cvet") setSelectedColorCodes(new Set(next))
            else if (key === "razmer") setSelectedRazmery(new Set(next))
            else if (key === "status") setSelectedChannelStatusIds(new Set(next.map((v) => Number(v))))
          }}
          onResetAll={() => {
            setSelectedModelKods(new Set())
            setSelectedColorCodes(new Set())
            setSelectedRazmery(new Set())
            setSelectedChannelStatusIds(new Set())
          }}
        />
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
              {effectiveColumns.map((key) => (
                <col key={key} style={{ width: `${widthForColumn(key)}px` }} />
              ))}
            </colgroup>
            <thead className="bg-stone-50/80 border-b border-stone-200 sticky top-0 z-10">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="px-3 py-2.5 cat-sticky-col-checkbox cat-sticky-col-head">
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
                {effectiveColumns.map((key, idx) => {
                  const label = labelForColumn(key)
                  // W9.7 — первая (якорная) data-колонка sticky на left:40 (после checkbox).
                  const stickyCls = idx === 0 ? " cat-sticky-col cat-sticky-col-offset cat-sticky-col-head" : ""
                  const baseCls = `relative px-3 py-2.5 font-medium whitespace-nowrap${stickyCls}`
                  // status_channel — не сортируемая (синтетика). Resizer привязан
                  // к исходной канальной колонке status_<channel>.
                  const resizerKey =
                    key === STATUS_CHANNEL_KEY && selectedChannel
                      ? `status_${selectedChannel}`
                      : key
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
                        {label}
                        <span {...bindResizer(resizerKey)} />
                      </SortableHeader>
                    )
                  }
                  return (
                    <th key={key} className={baseCls}>
                      {label}
                      <span {...bindResizer(resizerKey)} />
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {visibleByGroup.map((group) => {
                const collapsed = groupBy !== "none" && isGroupCollapsed(group.key)
                return (
                <React.Fragment key={group.key}>
                  {groupBy !== "none" && (
                    <tr className="bg-stone-50 border-b border-stone-200 sticky top-[36px] z-[1]">
                      <td colSpan={effectiveColumns.length + 1} className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => toggleGroupCollapsed(group.key)}
                          className="flex items-baseline gap-2 w-full text-left hover:opacity-80 transition-opacity"
                          aria-expanded={!collapsed}
                          aria-label={collapsed ? `Развернуть группу ${group.label || "—"}` : `Свернуть группу ${group.label || "—"}`}
                        >
                          {collapsed
                            ? <ChevronRight className="w-3.5 h-3.5 text-stone-500 self-center shrink-0" />
                            : <ChevronDown className="w-3.5 h-3.5 text-stone-500 self-center shrink-0" />}
                          <h3 className="cat-font-serif italic text-base text-stone-800">
                            {group.label || "—"}
                          </h3>
                          <span className="text-[11px] text-stone-400 tabular-nums">
                            {group.items.length} SKU
                          </span>
                        </button>
                      </td>
                    </tr>
                  )}
                  {!collapsed && group.visibleItems.map((t) => (
                    <tr
                      key={t.id}
                      className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60"
                    >
                      <td className="px-3 py-2.5 cat-sticky-col-checkbox">
                        <input
                          type="checkbox"
                          className="rounded border-stone-300"
                          checked={selected.has(t.barkod)}
                          onChange={() => toggleRow(t.barkod)}
                        />
                      </td>
                      {effectiveColumns.map((key, idx) => (
                        <td
                          key={key}
                          className={`px-3 py-2.5 whitespace-nowrap${idx === 0 ? " cat-sticky-col cat-sticky-col-offset" : ""}`}
                        >
                          {renderCell(key, t, cellCtx)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </React.Fragment>
                )
              })}
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
