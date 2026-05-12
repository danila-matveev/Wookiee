import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  X, Edit3, Archive, ChevronRight, ExternalLink, Save,
} from "lucide-react"
import {
  fetchColorDetailByCode,
  fetchCvetaWithUsage,
  fetchSemeystvaCvetov,
  fetchStatusy,
  updateCvet,
  deleteCvet,
  type ColorDetail,
  type ColorDetailArtikul,
  type CvetRow,
} from "@/lib/catalog/service"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import {
  resolveSwatch, isValidHex, findSimilarColors,
} from "@/lib/catalog/color-utils"
import { CvetEditModal } from "./colors-edit"

interface ColorCardProps {
  colorCode: string
  onClose: () => void
  onOpenColor: (code: string) => void
  onOpenModel: (modelOsnovaKod: string) => void
}

type Tab = "artikuly" | "modeli"

export function ColorCard({ colorCode, onClose, onOpenColor, onOpenModel }: ColorCardProps) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>("artikuly")
  const [editing, setEditing] = useState(false)

  // Esc closes the card
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !editing) onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose, editing])

  const { data, isLoading, error } = useQuery({
    queryKey: ["color-detail-by-code", colorCode],
    queryFn: () => fetchColorDetailByCode(colorCode),
    staleTime: 60 * 1000,
  })
  const { data: allCveta } = useQuery({
    queryKey: ["cveta-with-usage"],
    queryFn: fetchCvetaWithUsage,
    staleTime: 3 * 60 * 1000,
  })
  const { data: semeystva } = useQuery({
    queryKey: ["semeystva-cvetov"],
    queryFn: fetchSemeystvaCvetov,
    staleTime: 10 * 60 * 1000,
  })
  const { data: statuses } = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 10 * 60 * 1000,
    select: (rows) => rows.filter((s) => s.tip === "color"),
  })

  const archive = useMutation({
    mutationFn: (id: number) => deleteCvet(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cveta-with-usage"] })
      qc.invalidateQueries({ queryKey: ["color-detail-by-code", colorCode] })
      onClose()
    },
  })

  const status = useMemo(() => {
    if (!data || data.status_id == null || !statuses) return null
    return statuses.find((s) => s.id === data.status_id) ?? null
  }, [data, statuses])

  const familyName = useMemo(() => {
    if (!data || !semeystva) return data?.semeystvo ?? null
    if (data.semeystvo_id) return semeystva.find((s) => s.id === data.semeystvo_id)?.nazvanie ?? null
    return semeystva.find((s) => s.kod === data.semeystvo)?.nazvanie ?? data.semeystvo ?? null
  }, [data, semeystva])

  const grouped = useMemo(() => {
    if (!data) return [] as { id: number | null; kod: string; count: number; sample: ColorDetailArtikul[] }[]
    const map = new Map<string, { id: number | null; kod: string; count: number; sample: ColorDetailArtikul[] }>()
    for (const a of data.artikuly) {
      const key = a.model_osnova_kod ?? "—"
      if (!map.has(key)) {
        map.set(key, {
          id: a.model_osnova_id ?? null,
          kod: key,
          count: 0,
          sample: [],
        })
      }
      const g = map.get(key)!
      g.count += 1
      if (g.sample.length < 6) g.sample.push(a)
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count)
  }, [data])

  const similar = useMemo(() => {
    if (!data || !allCveta) return [] as CvetRow[]
    const pool = allCveta.filter((c) => c.color_code !== data.color_code)
    return findSimilarColors({ hex: data.hex }, pool, 6)
  }, [data, allCveta])

  return (
    <div
      className="fixed inset-0 z-50 bg-elevated/40 flex items-stretch justify-stretch"
      onClick={onClose}
    >
      <div
        className="absolute inset-4 sm:inset-8 bg-surface rounded-xl shadow-2xl overflow-hidden flex flex-col border border-default"
        onClick={(e) => e.stopPropagation()}
      >
        {isLoading && (
          <div className="flex-1 flex items-center justify-center text-label text-sm">Загрузка…</div>
        )}
        {error && (
          <div className="flex-1 flex items-center justify-center text-red-500 text-sm">Ошибка загрузки цвета</div>
        )}
        {data && !error && (
          <>
            <Header
              data={data}
              status={status}
              familyName={familyName}
              onClose={onClose}
              onEdit={() => setEditing(true)}
              onArchive={() => {
                if (window.confirm(`Перевести «${data.color_code}» в архив?`)) {
                  archive.mutate(data.id)
                }
              }}
            />

            <div className="border-b border-default px-6 flex gap-1 shrink-0">
              {([
                { id: "artikuly" as const, label: "Артикулы", count: data.artikuly.length },
                { id: "modeli" as const, label: "Модели использующие цвет", count: grouped.length },
              ]).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`relative px-3 py-2.5 text-sm transition-colors ${tab === t.id ? "text-primary font-medium" : "text-muted hover:text-primary"}`}
                >
                  {t.label}
                  <span className="ml-1.5 text-[10px] tabular-nums text-label">{t.count}</span>
                  {tab === t.id && <span className="absolute bottom-0 left-0 right-0 h-px bg-elevated" />}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-auto">
              <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-3 gap-6">
                <div className="col-span-2 space-y-4">
                  {tab === "artikuly" && (
                    <ArtikulyTab
                      artikuly={data.artikuly}
                      statuses={statuses ?? []}
                      onOpenModel={onOpenModel}
                    />
                  )}
                  {tab === "modeli" && (
                    <ModeliTab
                      grouped={grouped}
                      onOpenModel={onOpenModel}
                    />
                  )}
                </div>

                <Sidebar
                  data={data}
                  similar={similar}
                  onOpenColor={onOpenColor}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {editing && data && (
        <CvetEditModal
          initial={data}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
  )
}

// ─── Header ──────────────────────────────────────────────────────────────

function Header({
  data, status, familyName, onClose, onEdit, onArchive,
}: {
  data: ColorDetail
  status: { id: number; nazvanie: string; color: string | null } | null
  familyName: string | null
  onClose: () => void
  onEdit: () => void
  onArchive: () => void
}) {
  return (
    <div className="border-b border-default bg-surface shrink-0 px-6 py-4 flex items-center gap-4">
      <ColorSwatch hex={resolveSwatch(data.hex, data.color_code)} size={40} />
      <div className="flex-1">
        <div className="text-xs text-label mb-0.5">
          Цвет{familyName ? ` · семейство ${familyName}` : ""}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-medium text-primary font-serif italic">{data.color_code}</h1>
          {data.cvet && <span className="text-secondary">{data.cvet}</span>}
          {data.color && <span className="text-label text-sm">{data.color}</span>}
          {status && <StatusBadge status={status} compact />}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onEdit}
          className="px-3 py-1.5 text-xs text-secondary hover:bg-surface-muted rounded-md flex items-center gap-1.5"
        >
          <Edit3 className="w-3.5 h-3.5" /> Редактировать
        </button>
        <button
          onClick={onArchive}
          className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-md flex items-center gap-1.5"
        >
          <Archive className="w-3.5 h-3.5" /> Архивировать
        </button>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-surface-muted rounded-md"
          aria-label="Close"
        >
          <X className="w-4 h-4 text-muted" />
        </button>
      </div>
    </div>
  )
}

// ─── Artikuly tab ────────────────────────────────────────────────────────

function ArtikulyTab({
  artikuly, statuses, onOpenModel,
}: {
  artikuly: ColorDetailArtikul[]
  statuses: { id: number; nazvanie: string; color: string | null; tip: string }[]
  onOpenModel: (modelOsnovaKod: string) => void
}) {
  if (!artikuly.length) {
    return <div className="text-sm text-label italic">Нет артикулов с этим цветом</div>
  }
  return (
    <div className="bg-surface rounded-lg border border-default overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-page/80 border-b border-default">
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
            <th className="px-3 py-2 font-medium">Артикул</th>
            <th className="px-3 py-2 font-medium">Базовая модель</th>
            <th className="px-3 py-2 font-medium">Вариация</th>
            <th className="px-3 py-2 font-medium">Статус</th>
            <th className="px-3 py-2 font-medium">WB номенкл.</th>
            <th className="px-3 py-2 font-medium">OZON</th>
            <th className="px-3 py-2 font-medium text-right">SKU</th>
          </tr>
        </thead>
        <tbody>
          {artikuly.map((a) => {
            const status = statuses.find((s) => s.id === a.status_id) ?? null
            return (
              <tr key={a.id} className="border-b border-subtle last:border-0 hover:bg-page/60">
                <td className="px-3 py-2 font-mono text-xs text-primary">{a.artikul}</td>
                <td className="px-3 py-2">
                  {a.model_osnova_kod ? (
                    <button
                      onClick={() => onOpenModel(a.model_osnova_kod!)}
                      className="font-mono text-xs font-medium text-primary hover:underline inline-flex items-center gap-1"
                    >
                      {a.model_osnova_kod}
                      <ExternalLink className="w-3 h-3 text-label" />
                    </button>
                  ) : <span className="text-label">—</span>}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">{a.model_kod ?? "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={status} compact /></td>
                <td className="px-3 py-2 font-mono text-[11px] text-muted tabular-nums">{a.nomenklatura_wb ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-[11px] text-muted">{a.artikul_ozon ?? "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums text-secondary">{a.tovary_cnt}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ─── Modeli tab ──────────────────────────────────────────────────────────

function ModeliTab({
  grouped, onOpenModel,
}: {
  grouped: { id: number | null; kod: string; count: number; sample: ColorDetailArtikul[] }[]
  onOpenModel: (modelOsnovaKod: string) => void
}) {
  if (!grouped.length) {
    return <div className="text-sm text-label italic">Цвет не используется ни в одной модели</div>
  }
  return (
    <div className="space-y-2">
      {grouped.map((g) => (
        <button
          key={g.kod}
          onClick={() => onOpenModel(g.kod)}
          className="w-full flex items-center justify-between p-3 bg-page hover:bg-surface-muted rounded-md text-left transition-colors"
        >
          <div>
            <div className="font-mono text-sm text-primary">{g.kod}</div>
            <div className="text-xs text-muted mt-0.5">
              {g.sample.slice(0, 4).map((a) => a.artikul).join(" · ")}
              {g.count > 4 && ` · ещё ${g.count - 4}`}
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-secondary">
            <span><span className="font-medium text-primary">{g.count}</span> арт.</span>
            <ChevronRight className="w-3.5 h-3.5 text-label" />
          </div>
        </button>
      ))}
    </div>
  )
}

// ─── Sidebar ─────────────────────────────────────────────────────────────

function SidebarBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface rounded-lg border border-default p-4">
      <div className="text-[11px] uppercase tracking-wider text-label mb-3">{title}</div>
      {children}
    </div>
  )
}

function Sidebar({
  data, similar, onOpenColor,
}: {
  data: ColorDetail
  similar: CvetRow[]
  onOpenColor: (code: string) => void
}) {
  const qc = useQueryClient()
  const [editingHex, setEditingHex] = useState(false)
  const [hex, setHex] = useState(data.hex ?? "")

  useEffect(() => { setHex(data.hex ?? "") }, [data.hex])

  const update = useMutation({
    mutationFn: (newHex: string) => updateCvet(data.id, { hex: newHex || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cveta-with-usage"] })
      qc.invalidateQueries({ queryKey: ["color-detail-by-code", data.color_code] })
      setEditingHex(false)
    },
  })

  const previewHex = isValidHex(hex) ? hex : resolveSwatch(data.hex, data.color_code)
  const totalSku = data.artikuly.reduce((s, a) => s + a.tovary_cnt, 0)

  return (
    <div className="col-span-1 space-y-4">
      <SidebarBlock title="HEX">
        <div className="flex items-center gap-3">
          <div
            className="w-16 h-16 rounded-md ring-1 ring-[var(--color-border-default)] shrink-0"
            style={{ background: previewHex }}
          />
          <div className="flex-1">
            <div className="font-mono text-sm text-primary">{data.hex ?? "—"}</div>
            <div className="text-xs text-muted mt-1">
              {isValidHex(data.hex) ? "DB-точный" : "автогенерация"}
            </div>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <input
            type="color"
            value={isValidHex(hex) ? hex : "#000000"}
            onChange={(e) => { setHex(e.target.value); setEditingHex(true) }}
            className="w-10 h-9 rounded-md border border-default bg-surface p-0 cursor-pointer"
            aria-label="Hex picker"
          />
          <input
            type="text"
            value={hex}
            placeholder="#RRGGBB"
            onChange={(e) => { setHex(e.target.value); setEditingHex(true) }}
            className="flex-1 px-2.5 py-1.5 text-sm font-mono border border-default rounded-md bg-surface outline-none focus:border-[var(--color-border-strong)]"
          />
          {editingHex && (
            <button
              onClick={() => update.mutate(hex)}
              disabled={update.isPending || (!!hex && !isValidHex(hex))}
              className="px-2 py-1.5 text-xs text-white bg-elevated hover:bg-surface rounded-md disabled:opacity-50 flex items-center gap-1"
            >
              <Save className="w-3 h-3" /> Сохранить
            </button>
          )}
        </div>
      </SidebarBlock>

      <SidebarBlock title="Использование">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Моделей</span>
            <span className="font-medium tabular-nums">{data.modeli_cnt}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Артикулов</span>
            <span className="font-medium tabular-nums">{data.artikuly_cnt}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">SKU</span>
            <span className="font-medium tabular-nums">{totalSku}</span>
          </div>
        </div>
      </SidebarBlock>

      <SidebarBlock title="Атрибуты">
        <div className="space-y-2 text-sm">
          {data.lastovica && (
            <div className="flex justify-between">
              <span className="text-muted">Ластовица</span>
              <span className="text-primary">{data.lastovica}</span>
            </div>
          )}
          {!data.lastovica && (
            <div className="text-xs text-label italic">Ластовица не задана</div>
          )}
        </div>
      </SidebarBlock>

      <SidebarBlock title="Похожие цвета">
        {similar.length === 0 ? (
          <div className="text-xs text-label italic">
            {isValidHex(data.hex) ? "Не найдено цветов с похожим HEX" : "Нет HEX — похожие не вычислить"}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {similar.map((c) => (
              <button
                key={c.id}
                onClick={() => onOpenColor(c.color_code)}
                className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-page transition-colors group"
                title={`${c.color_code}${c.cvet ? ` · ${c.cvet}` : ""}`}
              >
                <ColorSwatch hex={resolveSwatch(c.hex, c.color_code)} size={36} />
                <div className="text-[10px] font-mono text-secondary group-hover:text-primary truncate w-full text-center">
                  {c.color_code}
                </div>
              </button>
            ))}
          </div>
        )}
      </SidebarBlock>
    </div>
  )
}

