import { useCallback, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Search, Plus, MoreHorizontal, Edit3, Archive } from "lucide-react"
import {
  fetchCvetaWithUsage,
  fetchSemeystvaCvetov,
  fetchStatusy,
  getCatalogAssetSignedUrl,
  deleteCvet,
  type CvetRow,
  type SemeystvoCveta,
} from "@/lib/catalog/service"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { CellText } from "@/components/catalog/ui/cell-text"
import { FilterBar } from "@/components/catalog/ui/filter-bar"
import { resolveSwatch } from "@/lib/catalog/color-utils"
import { ColorCard } from "./color-card"
import { CvetEditModal } from "./colors-edit"
import { SyncMirrorButton } from "@/components/catalog/sync-mirror-button"

// ─── Hooks ───────────────────────────────────────────────────────────────

function useColorStatuses() {
  return useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 10 * 60 * 1000,
    select: (rows) => rows.filter((s) => s.tip === "color"),
  })
}

function useSemeystva() {
  return useQuery<SemeystvoCveta[]>({
    queryKey: ["semeystva-cvetov"],
    queryFn: fetchSemeystvaCvetov,
    staleTime: 10 * 60 * 1000,
  })
}

// ─── Family table block ──────────────────────────────────────────────────

interface FamilyTableProps {
  title: string
  description: string | null
  items: CvetRow[]
  statusById: Map<number, { id: number; nazvanie: string; color: string | null }>
  onOpen: (code: string) => void
  onEdit: (row: CvetRow) => void
  onArchive: (row: CvetRow) => void
}

function FamilyTable({ title, description, items, statusById, onOpen, onEdit, onArchive }: FamilyTableProps) {
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-2">
        <span className="font-medium text-stone-700">{title}</span>
        <span className="text-stone-300">·</span>
        <span className="tabular-nums">{items.length}</span>
        {description && (
          <span className="text-stone-400 italic font-normal text-[11px]">{description}</span>
        )}
      </h3>
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        {/* W10.2 — min-w даёт горизонтальный скролл при недостатке viewport-а. */}
        <table className="w-full text-sm min-w-[1000px]">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2 font-medium w-10" />
              <th className="px-3 py-2 font-medium">Color Code</th>
              <th className="px-3 py-2 font-medium">Цвет (RU)</th>
              <th className="px-3 py-2 font-medium">Color (EN)</th>
              <th className="px-3 py-2 font-medium">Ластовица</th>
              <th className="px-3 py-2 font-medium">Использован в</th>
              <th className="px-3 py-2 font-medium">Статус</th>
              <th className="px-3 py-2 font-medium w-10" />
            </tr>
          </thead>
          <tbody>
            {items.map((c) => {
              const status = c.status_id != null ? statusById.get(c.status_id) ?? null : null
              return (
                <tr
                  key={c.id}
                  onClick={() => onOpen(c.color_code)}
                  className="group border-b border-stone-100 last:border-0 hover:bg-stone-50/60 cursor-pointer"
                >
                  <td className="px-3 py-2"><SwatchOrPhoto cvet={c} /></td>
                  <td className="px-3 py-2">
                    <CellText className="font-mono text-stone-900" title={c.color_code}>
                      {c.color_code}
                    </CellText>
                  </td>
                  <td className="px-3 py-2">
                    <CellText title={c.cvet ?? ""}>{c.cvet ?? "—"}</CellText>
                  </td>
                  <td className="px-3 py-2 text-stone-500">
                    <CellText title={c.color ?? ""}>{c.color ?? "—"}</CellText>
                  </td>
                  <td className="px-3 py-2 text-stone-500">
                    <CellText title={c.lastovica ?? ""}>{c.lastovica ?? "—"}</CellText>
                  </td>
                  <td className="px-3 py-2 text-stone-600">
                    {c.modeli_cnt > 0 || c.artikuly_cnt > 0 ? (
                      <span>
                        <span className="font-medium text-stone-900">{c.modeli_cnt}</span> мод. ·{" "}
                        <span className="font-medium">{c.artikuly_cnt}</span> арт.
                      </span>
                    ) : (
                      <span className="text-stone-400 italic text-xs">не используется</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={status} compact />
                  </td>
                  <td className="px-3 py-2">
                    <RowMenu
                      onEdit={() => onEdit(c)}
                      onArchive={() => onArchive(c)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RowMenu({ onEdit, onArchive }: { onEdit: () => void; onArchive: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="p-1 rounded hover:bg-stone-100 opacity-0 group-hover:opacity-100 focus:opacity-100"
      >
        <MoreHorizontal className="w-4 h-4 text-stone-500" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 w-40 bg-white border border-stone-200 rounded-md shadow-lg z-20 py-1 text-sm">
            <button
              className="w-full px-3 py-1.5 text-left hover:bg-stone-50 flex items-center gap-2 text-stone-700"
              onClick={() => { setOpen(false); onEdit() }}
            >
              <Edit3 className="w-3.5 h-3.5" /> Редактировать
            </button>
            <button
              className="w-full px-3 py-1.5 text-left hover:bg-stone-50 flex items-center gap-2 text-red-600"
              onClick={() => { setOpen(false); onArchive() }}
            >
              <Archive className="w-3.5 h-3.5" /> В архив
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ─── Swatch or photo thumbnail ──────────────────────────────────────────

function SwatchOrPhoto({ cvet }: { cvet: CvetRow }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!cvet.image_url) {
      setUrl(null)
      return
    }
    let cancelled = false
    void getCatalogAssetSignedUrl(cvet.image_url)
      .then((u) => { if (!cancelled) setUrl(u) })
      .catch(() => { /* fallback to swatch */ })
    return () => { cancelled = true }
  }, [cvet.image_url])

  if (cvet.image_url && url) {
    return (
      <img
        src={url}
        alt={cvet.color_code}
        className="w-6 h-6 rounded object-cover ring-1 ring-stone-200"
      />
    )
  }
  return <ColorSwatch hex={cvet.hex} size={24} />
}

// ─── Colors list ─────────────────────────────────────────────────────────

function ColorsView({ onOpen }: { onOpen: (code: string) => void }) {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["cveta-with-usage"],
    queryFn: fetchCvetaWithUsage,
    staleTime: 3 * 60 * 1000,
  })
  const { data: semeystva } = useSemeystva()
  const { data: statuses } = useColorStatuses()

  const [search, setSearch] = useState("")
  // W10.31 — multi-select фильтры через FilterBar (раньше были single-select
  // chip-кнопки «Семейство: Все / Трикотаж / ...» и «Статус: Все / ...»).
  const [familyFilters, setFamilyFilters] = useState<Set<string>>(new Set())
  const [statusFilters, setStatusFilters] = useState<Set<number>>(new Set())
  const [editingRow, setEditingRow] = useState<CvetRow | "new" | null>(null)

  const archive = useMutation({
    mutationFn: (id: number) => deleteCvet(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cveta-with-usage"] }),
  })

  const statusById = useMemo(() => {
    const m = new Map<number, { id: number; nazvanie: string; color: string | null }>()
    for (const s of statuses ?? []) m.set(s.id, s)
    return m
  }, [statuses])

  const semeystvaById = useMemo(() => {
    const m = new Map<number, SemeystvoCveta>()
    for (const s of semeystva ?? []) m.set(s.id, s)
    return m
  }, [semeystva])

  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (familyFilters.size > 0) {
      res = res.filter((c) => {
        const fam = c.semeystvo_id ? semeystvaById.get(c.semeystvo_id)?.kod : c.semeystvo
        return fam != null && familyFilters.has(fam)
      })
    }
    if (statusFilters.size > 0) {
      res = res.filter((c) => c.status_id != null && statusFilters.has(c.status_id))
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter((c) =>
        c.color_code.toLowerCase().includes(q) ||
        (c.cvet ?? "").toLowerCase().includes(q) ||
        (c.color ?? "").toLowerCase().includes(q),
      )
    }
    return res
  }, [data, familyFilters, statusFilters, search, semeystvaById])

  // W10.31 — counts для FilterBar (отображаются справа от опции в popover).
  // Считаем по всему датасету `data`, не по `filtered`, чтобы значения не
  // «прыгали» при выборе одного из фильтров.
  const familyCounts = useMemo(() => {
    const acc = new Map<string, number>()
    for (const c of data ?? []) {
      const fam = c.semeystvo_id ? semeystvaById.get(c.semeystvo_id)?.kod : c.semeystvo
      if (fam) acc.set(fam, (acc.get(fam) ?? 0) + 1)
    }
    return acc
  }, [data, semeystvaById])

  const statusCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const c of data ?? []) {
      if (c.status_id != null) acc.set(c.status_id, (acc.get(c.status_id) ?? 0) + 1)
    }
    return acc
  }, [data])

  const grouped = useMemo(() => {
    const families = (semeystva ?? [])
    const groups = families.map((s) => {
      const items = filtered.filter((c) => {
        const code = c.semeystvo_id ? semeystvaById.get(c.semeystvo_id)?.kod : c.semeystvo
        return code === s.kod
      })
      return { family: s, items }
    }).filter((g) => g.items.length > 0)

    const familyCodes = new Set(families.map((s) => s.kod))
    const orphans = filtered.filter((c) => {
      const code = c.semeystvo_id ? semeystvaById.get(c.semeystvo_id)?.kod : c.semeystvo
      return !code || !familyCodes.has(code)
    })
    return { groups, orphans }
  }, [filtered, semeystva, semeystvaById])

  if (isLoading) return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  if (error) return <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки цветов</div>

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1 className="text-3xl text-stone-900 cat-font-serif italic">Цвета</h1>
            <div className="text-sm text-stone-500 mt-1">
              {data?.length ?? 0} цветов · группировка по семейству
            </div>
          </div>
          <div className="flex items-center gap-2">
            <SyncMirrorButton />
            <button
              onClick={() => setEditingRow("new")}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Новый цвет
            </button>
          </div>
        </div>
      </div>

      <div className="px-6 pb-3 flex items-center gap-2 shrink-0 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по коду, RU, EN…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>

        {/* W10.31 — компактные Notion-style multi-select dropdown'ы
            (см. /matrix). Раньше тут был длинный ряд chip-кнопок
            «Семейство: Все/Трикотаж/Jelly/...» и «Статус: Все/...» —
            single-select, без поиска, занимал две строки на широком экране. */}
        <FilterBar
          filters={[
            {
              key: "family",
              label: "Семейство",
              options: (semeystva ?? []).map((s) => ({
                value: s.kod,
                label: s.nazvanie,
                count: familyCounts.get(s.kod) ?? 0,
              })),
            },
            {
              key: "status",
              label: "Статус",
              options: (statuses ?? []).map((s) => ({
                value: String(s.id),
                label: s.nazvanie,
                count: statusCounts.get(s.id) ?? 0,
              })),
            },
          ]}
          values={{
            family: Array.from(familyFilters),
            status: Array.from(statusFilters).map(String),
          }}
          onChange={(key, next) => {
            if (key === "family") setFamilyFilters(new Set(next))
            else if (key === "status") setStatusFilters(new Set(next.map((v) => Number(v))))
          }}
          onResetAll={() => {
            setFamilyFilters(new Set())
            setStatusFilters(new Set())
          }}
        />

        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {data?.length ?? 0}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 pb-6 space-y-6">
        {grouped.groups.map((g) => (
          <FamilyTable
            key={g.family.kod}
            title={g.family.nazvanie}
            description={g.family.opisanie}
            items={g.items}
            statusById={statusById}
            onOpen={onOpen}
            onEdit={(row) => setEditingRow(row)}
            onArchive={(row) => {
              if (window.confirm(`Перевести «${row.color_code}» в архив?`)) {
                archive.mutate(row.id)
              }
            }}
          />
        ))}
        {grouped.orphans.length > 0 && (
          <FamilyTable
            title="Без семейства"
            description="Назначь семейство в карточке цвета"
            items={grouped.orphans}
            statusById={statusById}
            onOpen={onOpen}
            onEdit={(row) => setEditingRow(row)}
            onArchive={(row) => {
              if (window.confirm(`Перевести «${row.color_code}» в архив?`)) {
                archive.mutate(row.id)
              }
            }}
          />
        )}
        {filtered.length === 0 && (
          <div className="py-8 text-center text-sm text-stone-400 italic">Ничего не найдено</div>
        )}
      </div>

      {editingRow && (
        <CvetEditModal
          initial={editingRow === "new" ? null : editingRow}
          onClose={() => setEditingRow(null)}
        />
      )}
    </div>
  )
}

// ─── ColorsPage ──────────────────────────────────────────────────────────

export function ColorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const colorCode = searchParams.get("color")
  const modelCode = searchParams.get("model")

  const openColor = useCallback((code: string) => {
    setSearchParams({ color: code })
  }, [setSearchParams])

  const closeColor = useCallback(() => {
    setSearchParams({})
  }, [setSearchParams])

  const openModelByCode = useCallback((code: string) => {
    // Navigate to matrix with selected base model code
    window.location.href = `/catalog/matrix?model=${encodeURIComponent(code)}`
  }, [])

  return (
    <>
      <ColorsView onOpen={openColor} />
      {colorCode && !modelCode && (
        <ColorCard
          colorCode={colorCode}
          onClose={closeColor}
          onOpenColor={openColor}
          onOpenModel={openModelByCode}
        />
      )}
    </>
  )
}
