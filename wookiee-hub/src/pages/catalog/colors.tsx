import { useCallback, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Search, Plus, MoreHorizontal, Edit3, Archive } from "lucide-react"
import {
  fetchCvetaWithUsage,
  fetchSemeystvaCvetov,
  fetchStatusy,
  deleteCvet,
  type CvetRow,
  type SemeystvoCveta,
} from "@/lib/catalog/service"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { resolveSwatch } from "@/lib/catalog/color-utils"
import { ColorCard } from "./color-card"
import { CvetEditModal } from "./colors-edit"

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
      <h3 className="text-xs uppercase tracking-wider text-muted mb-2 flex items-center gap-2">
        <span className="font-medium text-secondary">{title}</span>
        <span className="text-label">·</span>
        <span className="tabular-nums">{items.length}</span>
        {description && (
          <span className="text-label italic font-normal text-[11px]">{description}</span>
        )}
      </h3>
      <div className="bg-surface rounded-lg border border-default overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-page/80 border-b border-default">
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
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
                  className="group border-b border-subtle last:border-0 hover:bg-page/60 cursor-pointer"
                >
                  <td className="px-3 py-2"><ColorSwatch hex={resolveSwatch(c.hex, c.color_code)} size={24} /></td>
                  <td className="px-3 py-2"><span className="font-mono text-primary">{c.color_code}</span></td>
                  <td className="px-3 py-2">{c.cvet ?? "—"}</td>
                  <td className="px-3 py-2 text-muted">{c.color ?? "—"}</td>
                  <td className="px-3 py-2 text-muted">{c.lastovica ?? "—"}</td>
                  <td className="px-3 py-2 text-secondary">
                    {c.modeli_cnt > 0 || c.artikuly_cnt > 0 ? (
                      <span>
                        <span className="font-medium text-primary">{c.modeli_cnt}</span> мод. ·{" "}
                        <span className="font-medium">{c.artikuly_cnt}</span> арт.
                      </span>
                    ) : (
                      <span className="text-label italic text-xs">не используется</span>
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
        className="p-1 rounded hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus:opacity-100"
      >
        <MoreHorizontal className="w-4 h-4 text-muted" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 w-40 bg-surface border border-default rounded-md shadow-lg z-20 py-1 text-sm">
            <button
              className="w-full px-3 py-1.5 text-left hover:bg-page flex items-center gap-2 text-secondary"
              onClick={() => { setOpen(false); onEdit() }}
            >
              <Edit3 className="w-3.5 h-3.5" /> Редактировать
            </button>
            <button
              className="w-full px-3 py-1.5 text-left hover:bg-page flex items-center gap-2 text-red-600"
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
  const [familyFilter, setFamilyFilter] = useState<"all" | string>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
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
    if (familyFilter !== "all") {
      res = res.filter((c) => {
        const fam = c.semeystvo_id ? semeystvaById.get(c.semeystvo_id)?.kod : c.semeystvo
        return fam === familyFilter
      })
    }
    if (statusFilter !== "all") {
      res = res.filter((c) => c.status_id === statusFilter)
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
  }, [data, familyFilter, statusFilter, search, semeystvaById])

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

  if (isLoading) return <div className="px-6 py-8 text-sm text-label">Загрузка…</div>
  if (error) return <div className="px-6 py-8 text-sm text-red-500">Ошибка загрузки цветов</div>

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-label mb-1">Каталог</div>
            <h1 className="text-3xl text-primary font-serif italic">Цвета</h1>
            <div className="text-sm text-muted mt-1">
              {data?.length ?? 0} цветов · группировка по семейству
            </div>
          </div>
          <button
            onClick={() => setEditingRow("new")}
            className="px-3 py-1.5 text-xs text-white bg-elevated hover:bg-surface rounded-md flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Новый цвет
          </button>
        </div>
      </div>

      <div className="px-6 pb-3 flex items-center gap-2 shrink-0 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-label absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по коду, RU, EN…"
            className="pl-8 pr-3 py-1.5 text-sm border border-default rounded-md bg-surface outline-none focus:border-[var(--color-border-strong)] w-72"
          />
        </div>

        <span className="text-xs text-muted mx-1">Семейство:</span>
        <button
          onClick={() => setFamilyFilter("all")}
          className={`px-2.5 py-1 text-xs rounded-md transition-colors ${familyFilter === "all" ? "bg-elevated text-white" : "text-secondary hover:bg-surface-muted"}`}
        >Все</button>
        {(semeystva ?? []).map((s) => (
          <button
            key={s.kod}
            onClick={() => setFamilyFilter(s.kod)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${familyFilter === s.kod ? "bg-elevated text-white" : "text-secondary hover:bg-surface-muted"}`}
          >{s.nazvanie}</button>
        ))}

        <span className="text-xs text-muted mx-1 ml-3">Статус:</span>
        <button
          onClick={() => setStatusFilter("all")}
          className={`px-2.5 py-1 text-xs rounded-md transition-colors ${statusFilter === "all" ? "bg-elevated text-white" : "text-secondary hover:bg-surface-muted"}`}
        >Все</button>
        {(statuses ?? []).map((s) => (
          <button
            key={s.id}
            onClick={() => setStatusFilter(s.id)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${statusFilter === s.id ? "bg-elevated text-white" : "text-secondary hover:bg-surface-muted"}`}
          >{s.nazvanie}</button>
        ))}

        <div className="ml-auto text-xs text-muted tabular-nums">
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
          <div className="py-8 text-center text-sm text-label italic">Ничего не найдено</div>
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
