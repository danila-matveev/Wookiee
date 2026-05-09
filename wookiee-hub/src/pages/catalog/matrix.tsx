import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertCircle,
  Archive,
  ArrowLeft,
  Building2,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  Info,
  Link2,
  MoreHorizontal,
  Plus,
  Search,
} from "lucide-react"
import {
  archiveModel,
  bulkUpdateModelStatus,
  createModel,
  duplicateModel,
  fetchArtikulyRegistry,
  fetchFabriki,
  fetchKategorii,
  fetchKollekcii,
  fetchMatrixList,
  fetchModelDetail,
  fetchStatusy,
  fetchTovaryRegistry,
  getUiPref,
  setUiPref,
  updateModel,
} from "@/lib/catalog/service"
import type { MatrixRow, ModelDetail } from "@/lib/catalog/service"
import { StatusBadge, CATALOG_STATUSES } from "@/components/catalog/ui/status-badge"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { Tooltip } from "@/components/catalog/ui/tooltip"
import { BulkActionsBar } from "@/components/catalog/ui/bulk-actions-bar"
import { LevelBadge, type Level } from "@/components/catalog/ui/level-badge"
import {
  swatchColor,
  relativeDate,
  ATTRIBUTES_BY_CATEGORY,
  ATTRIBUTE_LABELS,
} from "@/lib/catalog/color-utils"

// Standard razmer chip-pill ladder used in the table.
const RAZMER_LADDER = ["XS", "S", "M", "L", "XL", "XXL"] as const

// ─── Shared helpers ────────────────────────────────────────────────────────

function ColorSwatch({ colorCode, size = 16 }: { colorCode: string | null; size?: number }) {
  if (!colorCode) return <div className="rounded-full bg-stone-200" style={{ width: size, height: size }} />
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ width: size, height: size, background: swatchColor(colorCode) }}
    />
  )
}

function Section({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="font-medium text-stone-900 mb-1">{label}</div>
      {hint && <div className="text-xs text-stone-500 mb-4">{hint}</div>}
      {!hint && <div className="mb-4" />}
      {children}
    </div>
  )
}

function SidebarBlock({ title, badge, action, children }: {
  title: string; badge?: React.ReactNode; action?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-stone-400">
          {title} {badge}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function FieldWrap({
  label, children, hint, full, level,
}: {
  label: string
  children: React.ReactNode
  hint?: string
  full?: boolean
  level?: Level
}) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <div className="flex items-center gap-1.5 mb-1">
        <label className="block text-[11px] uppercase tracking-wider text-stone-500">{label}</label>
        {level && <LevelBadge level={level} />}
      </div>
      {children}
      {hint && <div className="text-[10px] text-stone-400 mt-1">{hint}</div>}
    </div>
  )
}

function ReadField({ value, mono }: { value: string | number | null | undefined; mono?: boolean }) {
  if (value === null || value === undefined || value === "") {
    return <div className="px-2.5 py-1.5 text-sm text-stone-400 italic">не задано</div>
  }
  return <div className={`px-2.5 py-1.5 text-sm text-stone-900 ${mono ? "font-mono" : ""}`}>{value}</div>
}

// ─── Editable field shells (used inside ModelCard edit mode) ──────────────

function EditTextField({
  value, onChange, mono, placeholder,
}: { value: string | number | null | undefined; onChange: (v: string) => void; mono?: boolean; placeholder?: string }) {
  return (
    <input
      type="text"
      value={value == null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 ${mono ? "font-mono" : ""}`}
    />
  )
}

function EditNumberField({
  value, onChange, suffix,
}: { value: number | null | undefined; onChange: (v: number | null) => void; suffix?: string }) {
  return (
    <div className="relative">
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => {
          const v = e.target.value
          onChange(v === "" ? null : parseFloat(v))
        }}
        className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 tabular-nums pr-10"
      />
      {suffix && (
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-stone-400">{suffix}</span>
      )}
    </div>
  )
}

function EditSelectField<T extends string | number>({
  value, onChange, options,
}: {
  value: T | null | undefined
  onChange: (v: T | null) => void
  options: { id: T; nazvanie: string }[]
}) {
  return (
    <select
      value={value == null ? "" : String(value)}
      onChange={(e) => {
        const raw = e.target.value
        if (raw === "") return onChange(null)
        const found = options.find((o) => String(o.id) === raw)
        if (found) onChange(found.id)
      }}
      className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
    >
      <option value="">— не выбрано —</option>
      {options.map((o) => (
        <option key={String(o.id)} value={String(o.id)}>{o.nazvanie}</option>
      ))}
    </select>
  )
}

const RAZMER_CHOICES = ["XS", "S", "M", "L", "XL", "XXL"] as const

/** Chip-pill toggle для размерной линейки.
 *  Read-mode: чипы серые с активными выделенными.  Edit: те же чипы, но кликабельны. */
function SizeLineupField({
  value, onChange, readonly,
}: { value: string | null | undefined; onChange?: (v: string) => void; readonly?: boolean }) {
  const tokens = (value ?? "")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
  const selected = new Set<string>(tokens)
  return (
    <div className="flex flex-wrap gap-1.5 px-0.5 py-1">
      {RAZMER_CHOICES.map((s) => {
        const active = selected.has(s)
        return (
          <button
            key={s}
            type="button"
            disabled={readonly}
            onClick={() => {
              if (readonly || !onChange) return
              const next = new Set(selected)
              if (next.has(s)) next.delete(s)
              else next.add(s)
              const ordered = RAZMER_CHOICES.filter((x) => next.has(x))
              onChange(ordered.join(", "))
            }}
            className={`min-w-[36px] h-7 px-2 rounded-md border text-xs font-medium transition ${
              active
                ? "bg-stone-900 text-white border-stone-900"
                : "bg-white text-stone-600 border-stone-300 " + (readonly ? "" : "hover:border-stone-400 cursor-pointer")
            } ${readonly ? "cursor-default" : ""}`}
          >
            {s}
          </button>
        )
      })}
    </div>
  )
}

/** Per-field "level" (Базовый / Вариация / Артикул / SKU) — определяет где поле редактируется. */
const FIELD_LEVEL: Record<string, Level> = {
  kod: "model",
  status_id: "model",
  kategoriya: "model",
  kategoriya_id: "model",
  kollekciya: "model",
  kollekciya_id: "model",
  tip_kollekcii: "model",
  fabrika: "model",
  fabrika_id: "model",
  razmery_modeli: "model",
  material: "model",
  sku_china: "model",
  sostav_syrya: "model",
  srok_proizvodstva: "model",
  kratnost_koroba: "model",
  ves_kg: "model",
  dlina_cm: "model",
  shirina_cm: "model",
  vysota_cm: "model",
  tnved: "model",
  gruppa_sertifikata: "model",
  nazvanie_etiketka: "model",
  nazvanie_sayt: "model",
  opisanie_sayt: "model",
  composition: "model",
  tegi: "model",
  notion_link: "model",
  upakovka: "model",
}

// ─── Model Card (5 tabs) — placeholder until B3 ships its replacement ─────

function ModelCard({ modelId, onBack }: { modelId: number; onBack: () => void }) {
  const [tab, setTab] = useState<"opisanie" | "atributy" | "artikuly" | "sku" | "kontent">("opisanie")
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState<Partial<ModelDetail> | null>(null)
  const [saving, setSaving] = useState(false)
  const queryClient = useQueryClient()

  const { data: m, isLoading, error } = useQuery({
    queryKey: ["model-detail", modelId],
    queryFn: () => fetchModelDetail(modelId),
    staleTime: 2 * 60 * 1000,
  })

  // Reference lookups for edit-mode selects.
  const kategoriiQ = useQuery({ queryKey: ["kategorii"], queryFn: fetchKategorii, staleTime: 10 * 60 * 1000 })
  const kollekciiQ = useQuery({ queryKey: ["kollekcii"], queryFn: fetchKollekcii, staleTime: 10 * 60 * 1000 })
  const fabrikiQ = useQuery({ queryKey: ["fabriki"], queryFn: fetchFabriki, staleTime: 10 * 60 * 1000 })
  const statusyQ = useQuery({ queryKey: ["statusy"], queryFn: fetchStatusy, staleTime: 30 * 60 * 1000 })

  // Reset draft whenever a fresh model loads.
  useEffect(() => {
    if (m && draft === null) {
      setDraft({})
    }
  }, [m, draft])

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
        Загрузка…
      </div>
    )
  }
  if (error || !m) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-500 text-sm">
        Ошибка загрузки модели
      </div>
    )
  }

  const allArts = m.modeli.flatMap((v) => v.artikuly)
  const allSku = allArts.flatMap((a) => a.tovary)
  const cvetaSet = new Set(allArts.map((a) => a.cvet_color_code).filter(Boolean))
  const attrKeys = ATTRIBUTES_BY_CATEGORY[m.kategoriya_id ?? 0] ?? []
  const attrFilled = attrKeys.filter((k) => (m as unknown as Record<string, unknown>)[k]).length

  // Effective values: draft overrides if editing.
  const effective: ModelDetail = isEditing && draft
    ? ({ ...m, ...draft } as ModelDetail)
    : m
  const dirty = isEditing && draft && Object.keys(draft).length > 0
  const setField = <K extends keyof ModelDetail>(key: K, value: ModelDetail[K]) => {
    setDraft((prev) => ({ ...(prev ?? {}), [key]: value }))
  }

  const startEdit = () => { setDraft({}); setIsEditing(true) }
  const cancelEdit = () => { setDraft({}); setIsEditing(false) }
  const saveEdit = async () => {
    if (!draft || Object.keys(draft).length === 0) {
      setIsEditing(false)
      return
    }
    setSaving(true)
    try {
      // Drop derived/relational fields the server does not accept.
      const allowedKeys = new Set([
        "kod", "status_id", "kategoriya_id", "kollekciya_id", "tip_kollekcii", "fabrika_id",
        "razmery_modeli", "material", "sku_china", "sostav_syrya", "srok_proizvodstva",
        "kratnost_koroba", "ves_kg", "dlina_cm", "shirina_cm", "vysota_cm",
        "tnved", "gruppa_sertifikata",
        "nazvanie_etiketka", "nazvanie_sayt", "opisanie_sayt", "composition", "tegi",
        "notion_link", "notion_strategy_link", "yandex_disk_link", "upakovka",
      ])
      const patch: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(draft)) {
        if (allowedKeys.has(k)) patch[k] = v
      }
      await updateModel(m.kod, patch as never)
      await queryClient.invalidateQueries({ queryKey: ["model-detail", modelId] })
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      setDraft({})
      setIsEditing(false)
    } catch (err) {
      window.alert(`Не удалось сохранить: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const headerDuplicate = async () => {
    const newKod = window.prompt(`Дублировать «${m.kod}»: введите новый kod`, `${m.kod}_copy`)
    if (!newKod) return
    try {
      await duplicateModel(m.kod, newKod.trim())
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      window.alert(`Создана модель ${newKod.trim()}`)
    } catch (err) {
      window.alert(`Не удалось дублировать: ${(err as Error).message}`)
    }
  }
  const headerArchive = async () => {
    const ok = window.confirm(`Архивировать «${m.kod}» и все связанные вариации/артикулы/SKU?`)
    if (!ok) return
    try {
      await archiveModel(m.kod)
      await queryClient.invalidateQueries({ queryKey: ["model-detail", modelId] })
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    } catch (err) {
      window.alert(`Не удалось архивировать: ${(err as Error).message}`)
    }
  }

  const TABS = [
    { id: "opisanie", label: "Описание" },
    { id: "atributy", label: "Атрибуты", count: `${attrFilled}/${attrKeys.length}` },
    { id: "artikuly", label: "Артикулы", count: allArts.length },
    { id: "sku", label: "SKU", count: allSku.length },
    { id: "kontent", label: "Контент и связи" },
  ] as const

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="border-b border-stone-200 bg-white shrink-0">
        <div className="px-6 py-4 flex items-center gap-4">
          <button onClick={onBack} className="p-1.5 hover:bg-stone-100 rounded-md">
            <ArrowLeft className="w-4 h-4 text-stone-700" />
          </button>
          <div className="flex-1">
            <div className="text-xs text-stone-400 mb-0.5">
              Базовая модель · {m.kategoriya ?? "—"}
              {isEditing && (
                <span className="ml-2 inline-flex items-center px-1.5 py-px rounded text-[10px] uppercase tracking-wider bg-amber-100 text-amber-800">
                  Черновик
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-medium text-stone-900 cat-font-serif">{m.kod}</h2>
              <StatusBadge statusId={effective.status_id ?? 0} />
              {effective.nazvanie_sayt && (
                <span className="text-sm text-stone-500 truncate max-w-[300px]">{effective.nazvanie_sayt}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <button
                  onClick={cancelEdit}
                  disabled={saving}
                  className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 disabled:opacity-60"
                >
                  Отмена
                </button>
                <button
                  onClick={saveEdit}
                  disabled={saving || !dirty}
                  className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5 disabled:opacity-60"
                >
                  {saving ? "Сохранение…" : "Сохранить"}
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={headerDuplicate}
                  className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
                >
                  <Copy className="w-3.5 h-3.5" /> Дублировать
                </button>
                <button
                  onClick={headerArchive}
                  className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
                >
                  <Archive className="w-3.5 h-3.5" /> В архив
                </button>
                <button
                  onClick={startEdit}
                  className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
                >
                  <Edit3 className="w-3.5 h-3.5" /> Редактировать
                </button>
              </>
            )}
          </div>
        </div>
        <div className="px-6 flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as typeof tab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                tab === t.id ? "text-stone-900 font-medium" : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              {"count" in t && t.count !== undefined && (
                <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              )}
              {tab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-3">
            {tab === "opisanie" && (
              <TabOpisanie
                m={effective}
                isEditing={isEditing}
                setField={setField}
                kategorii={kategoriiQ.data ?? []}
                kollekcii={kollekciiQ.data ?? []}
                fabriki={fabrikiQ.data ?? []}
                modelStatuses={(statusyQ.data ?? []).filter((s) => s.tip === "model")}
              />
            )}
            {tab === "atributy" && <TabAtributy m={effective} attrKeys={attrKeys} />}
            {tab === "artikuly" && <TabArtikuly m={m} />}
            {tab === "sku" && <TabSKU m={m} />}
            {tab === "kontent" && (
              <TabKontent
                m={effective}
                isEditing={isEditing}
                setField={setField}
              />
            )}
          </div>
          <div className="col-span-1 space-y-4">
            <SidebarBlock title="Заполненность">
              <div className="flex items-center gap-3">
                <CompletenessRing value={allSku.length > 0 ? 0.7 : 0.3} size={56} />
                <div>
                  <div className="text-2xl font-medium tabular-nums text-stone-900">{attrFilled}/{attrKeys.length}</div>
                  <div className="text-xs text-stone-500">атрибутов заполнено</div>
                </div>
              </div>
            </SidebarBlock>

            <SidebarBlock
              title="Вариации"
              badge={<span className="text-xs text-stone-500 tabular-nums">{m.modeli.length}</span>}
            >
              <div className="space-y-1">
                {m.modeli.map((v) => (
                  <div key={v.id} className="flex items-center justify-between py-1.5 px-2 -mx-2 hover:bg-stone-50 rounded text-sm">
                    <span className="font-mono text-stone-900">{v.kod}</span>
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">
                      {v.importer_nazvanie?.split(" ")[0] ?? "—"}
                    </span>
                  </div>
                ))}
                {m.modeli.length === 0 && (
                  <div className="text-sm text-stone-400 italic">Нет вариаций</div>
                )}
              </div>
            </SidebarBlock>

            <SidebarBlock
              title="Цвета модели"
              badge={<span className="text-xs text-stone-500 tabular-nums">{cvetaSet.size}</span>}
            >
              <div className="flex flex-wrap gap-1.5">
                {[...cvetaSet].slice(0, 20).map((code) => (
                  <div key={code} className="flex items-center gap-1.5 bg-stone-50 rounded px-1.5 py-1 text-xs">
                    <ColorSwatch colorCode={code} size={14} />
                    <span className="font-mono text-[10px] text-stone-700">{code}</span>
                  </div>
                ))}
                {cvetaSet.size > 20 && (
                  <span className="text-xs text-stone-400 self-center">+{cvetaSet.size - 20}</span>
                )}
              </div>
            </SidebarBlock>

            <SidebarBlock title="Метрики" >
              <div className="space-y-1.5 text-sm text-stone-400">
                <div className="flex justify-between">
                  <span>Остаток на складе</span><span className="tabular-nums">— шт</span>
                </div>
                <div className="flex justify-between">
                  <span>Оборачиваемость</span><span className="tabular-nums">— дн</span>
                </div>
                <div className="flex justify-between">
                  <span>Продаж за 30 дн</span><span className="tabular-nums">— шт</span>
                </div>
                <div className="text-[10px] italic mt-2 pt-2 border-t border-stone-100">
                  Данные подтянутся из МойСклад / WB API
                </div>
              </div>
            </SidebarBlock>
          </div>
        </div>
      </div>
    </div>
  )
}

interface TabOpisanieProps {
  m: ModelDetail
  isEditing: boolean
  setField: <K extends keyof ModelDetail>(key: K, value: ModelDetail[K]) => void
  kategorii: { id: number; nazvanie: string }[]
  kollekcii: { id: number; nazvanie: string }[]
  fabriki: { id: number; nazvanie: string }[]
  modelStatuses: { id: number; nazvanie: string; tip: string; color: string | null }[]
}

function TabOpisanie({ m, isEditing, setField, kategorii, kollekcii, fabriki, modelStatuses }: TabOpisanieProps) {
  return (
    <>
      <Section label="Основное">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="Код модели" level={FIELD_LEVEL.kod}>
            <ReadField value={m.kod} mono />
          </FieldWrap>
          <FieldWrap label="Статус" level={FIELD_LEVEL.status_id}>
            {isEditing ? (
              <EditSelectField<number>
                value={m.status_id ?? null}
                onChange={(v) => setField("status_id", v)}
                options={modelStatuses.map((s) => ({ id: s.id, nazvanie: s.nazvanie }))}
              />
            ) : (
              <div className="px-2.5 py-1.5"><StatusBadge statusId={m.status_id ?? 0} /></div>
            )}
          </FieldWrap>
          <FieldWrap label="Категория" level={FIELD_LEVEL.kategoriya}>
            {isEditing ? (
              <EditSelectField<number>
                value={m.kategoriya_id ?? null}
                onChange={(v) => setField("kategoriya_id", v)}
                options={kategorii}
              />
            ) : (
              <ReadField value={m.kategoriya} />
            )}
          </FieldWrap>
          <FieldWrap label="Коллекция" level={FIELD_LEVEL.kollekciya}>
            {isEditing ? (
              <EditSelectField<number>
                value={m.kollekciya_id ?? null}
                onChange={(v) => setField("kollekciya_id", v)}
                options={kollekcii}
              />
            ) : (
              <ReadField value={m.kollekciya} />
            )}
          </FieldWrap>
          <FieldWrap label="Тип коллекции" level={FIELD_LEVEL.tip_kollekcii}>
            {isEditing ? (
              <EditTextField value={m.tip_kollekcii} onChange={(v) => setField("tip_kollekcii", v)} />
            ) : (
              <ReadField value={m.tip_kollekcii} />
            )}
          </FieldWrap>
          <FieldWrap label="Фабрика" level={FIELD_LEVEL.fabrika}>
            {isEditing ? (
              <EditSelectField<number>
                value={m.fabrika_id ?? null}
                onChange={(v) => setField("fabrika_id", v)}
                options={fabriki}
              />
            ) : (
              <ReadField value={m.fabrika} />
            )}
          </FieldWrap>
        </div>
      </Section>
      <Section label="Производство">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="Размерная линейка" full level={FIELD_LEVEL.razmery_modeli}>
            <SizeLineupField
              value={m.razmery_modeli}
              onChange={(v) => setField("razmery_modeli", v)}
              readonly={!isEditing}
            />
          </FieldWrap>
          <FieldWrap label="Материал" level={FIELD_LEVEL.material}>
            {isEditing ? (
              <EditTextField value={m.material} onChange={(v) => setField("material", v)} />
            ) : (
              <ReadField value={m.material} />
            )}
          </FieldWrap>
          <FieldWrap label="SKU China" level={FIELD_LEVEL.sku_china}>
            {isEditing ? (
              <EditTextField value={m.sku_china} mono onChange={(v) => setField("sku_china", v)} />
            ) : (
              <ReadField value={m.sku_china} mono />
            )}
          </FieldWrap>
          <FieldWrap label="Состав сырья" full level={FIELD_LEVEL.sostav_syrya}>
            {isEditing ? (
              <EditTextField value={m.sostav_syrya} onChange={(v) => setField("sostav_syrya", v)} />
            ) : (
              <ReadField value={m.sostav_syrya} />
            )}
          </FieldWrap>
          <FieldWrap label="Срок производства" level={FIELD_LEVEL.srok_proizvodstva}>
            {isEditing ? (
              <EditTextField value={m.srok_proizvodstva} onChange={(v) => setField("srok_proizvodstva", v)} />
            ) : (
              <ReadField value={m.srok_proizvodstva} />
            )}
          </FieldWrap>
          <FieldWrap label="Кратность короба" level={FIELD_LEVEL.kratnost_koroba}>
            {isEditing ? (
              <EditNumberField
                value={m.kratnost_koroba}
                onChange={(v) => setField("kratnost_koroba", v as never)}
              />
            ) : (
              <ReadField value={m.kratnost_koroba} />
            )}
          </FieldWrap>
          <FieldWrap label="Вес, кг" level={FIELD_LEVEL.ves_kg}>
            {isEditing ? (
              <EditNumberField
                value={m.ves_kg}
                onChange={(v) => setField("ves_kg", v as never)}
                suffix="кг"
              />
            ) : (
              <ReadField value={m.ves_kg} mono />
            )}
          </FieldWrap>
          <FieldWrap label="Длина, см" level={FIELD_LEVEL.dlina_cm}>
            {isEditing ? (
              <EditNumberField
                value={m.dlina_cm}
                onChange={(v) => setField("dlina_cm", v as never)}
                suffix="см"
              />
            ) : (
              <ReadField value={m.dlina_cm} mono />
            )}
          </FieldWrap>
          <FieldWrap label="Ширина, см" level={FIELD_LEVEL.shirina_cm}>
            {isEditing ? (
              <EditNumberField
                value={m.shirina_cm}
                onChange={(v) => setField("shirina_cm", v as never)}
                suffix="см"
              />
            ) : (
              <ReadField value={m.shirina_cm} mono />
            )}
          </FieldWrap>
          <FieldWrap label="Высота, см" level={FIELD_LEVEL.vysota_cm}>
            {isEditing ? (
              <EditNumberField
                value={m.vysota_cm}
                onChange={(v) => setField("vysota_cm", v as never)}
                suffix="см"
              />
            ) : (
              <ReadField value={m.vysota_cm} mono />
            )}
          </FieldWrap>
        </div>
      </Section>
      <Section label="Юридическое">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="ТНВЭД" level={FIELD_LEVEL.tnved}>
            {isEditing ? (
              <EditTextField value={m.tnved} mono onChange={(v) => setField("tnved", v)} />
            ) : (
              <ReadField value={m.tnved} mono />
            )}
          </FieldWrap>
          <FieldWrap label="Группа сертификата" level={FIELD_LEVEL.gruppa_sertifikata}>
            {isEditing ? (
              <EditTextField value={m.gruppa_sertifikata} onChange={(v) => setField("gruppa_sertifikata", v)} />
            ) : (
              <ReadField value={m.gruppa_sertifikata} />
            )}
          </FieldWrap>
        </div>
      </Section>
    </>
  )
}

function TabAtributy({ m, attrKeys }: { m: ModelDetail; attrKeys: string[] }) {
  if (attrKeys.length === 0) {
    return (
      <Section label="Атрибуты">
        <div className="text-sm text-stone-400 italic">
          Для этой категории атрибуты не настроены
        </div>
      </Section>
    )
  }
  return (
    <Section
      label={`Атрибуты категории «${m.kategoriya ?? "—"}»`}
      hint={`${attrKeys.length} полей для данной категории`}
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-4">
        {attrKeys.map((key) => (
          <FieldWrap key={key} label={ATTRIBUTE_LABELS[key] ?? key} level="model">
            <ReadField value={(m as unknown as Record<string, unknown>)[key] as string | number | null | undefined} />
          </FieldWrap>
        ))}
      </div>
    </Section>
  )
}

function TabArtikuly({ m }: { m: ModelDetail }) {
  const allArts = m.modeli.flatMap((v) => v.artikuly.map((a) => ({ ...a, variantKod: v.kod })))
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
        <div>
          <div className="font-medium text-stone-900">Артикулы модели</div>
          <div className="text-xs text-stone-500">{allArts.length} артикулов</div>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-stone-50/80 border-b border-stone-200">
          <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
            <th className="px-3 py-2 font-medium">Артикул</th>
            <th className="px-3 py-2 font-medium">Вариация</th>
            <th className="px-3 py-2 font-medium">Цвет</th>
            <th className="px-3 py-2 font-medium">Статус</th>
            <th className="px-3 py-2 font-medium">WB номенкл.</th>
            <th className="px-3 py-2 font-medium">OZON</th>
            <th className="px-3 py-2 font-medium text-right">SKU</th>
          </tr>
        </thead>
        <tbody>
          {allArts.map((a) => (
            <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
              <td className="px-3 py-2 font-mono text-xs text-stone-700">{a.artikul}</td>
              <td className="px-3 py-2 font-mono text-xs text-stone-600">{a.variantKod}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <ColorSwatch colorCode={a.cvet_color_code} size={14} />
                  <span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span>
                  <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>
                </div>
              </td>
              <td className="px-3 py-2"><StatusBadge statusId={a.status_id ?? 0} compact /></td>
              <td className="px-3 py-2 font-mono text-[11px] text-stone-500 tabular-nums">
                {a.nomenklatura_wb ?? "—"}
              </td>
              <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                {a.artikul_ozon ?? "—"}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-stone-700">{a.tovary.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabSKU({ m }: { m: ModelDetail }) {
  const allSku = m.modeli.flatMap((v) =>
    v.artikuly.flatMap((a) =>
      a.tovary.map((t) => ({
        ...t,
        variantKod: v.kod,
        cvet_color_code: a.cvet_color_code,
      }))
    )
  )

  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200">
        <div className="font-medium text-stone-900">SKU модели</div>
        <div className="text-xs text-stone-500">{allSku.length} SKU</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2 font-medium">Баркод</th>
              <th className="px-3 py-2 font-medium">Вариация</th>
              <th className="px-3 py-2 font-medium">Цвет</th>
              <th className="px-3 py-2 font-medium">Размер</th>
              <th className="px-3 py-2 font-medium border-l border-stone-200">WB</th>
              <th className="px-3 py-2 font-medium">OZON</th>
              <th className="px-3 py-2 font-medium">Сайт</th>
              <th className="px-3 py-2 font-medium">Lamoda</th>
            </tr>
          </thead>
          <tbody>
            {allSku.slice(0, 100).map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-700">{t.barkod}</td>
                <td className="px-3 py-2 font-mono text-xs text-stone-600">{t.variantKod}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={t.cvet_color_code ?? null} size={14} />
                    <span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span>
                  </div>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{t.razmer_nazvanie ?? "—"}</td>
                <td className="px-3 py-2 border-l border-stone-100">
                  <StatusBadge statusId={t.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_ozon_id ?? 0} compact /></td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_sayt_id ?? 0} compact /></td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_lamoda_id ?? 0} compact /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {allSku.length > 100 && (
        <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
          Показаны первые 100 из {allSku.length}.
        </div>
      )}
    </div>
  )
}

interface TabKontentProps {
  m: ModelDetail
  isEditing: boolean
  setField: <K extends keyof ModelDetail>(key: K, value: ModelDetail[K]) => void
}

function TabKontent({ m, isEditing, setField }: TabKontentProps) {
  return (
    <>
      <Section label="Контент">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">
            <FieldWrap label="Название на этикетке" level={FIELD_LEVEL.nazvanie_etiketka}>
              {isEditing ? (
                <EditTextField value={m.nazvanie_etiketka} onChange={(v) => setField("nazvanie_etiketka", v)} />
              ) : (
                <ReadField value={m.nazvanie_etiketka} />
              )}
            </FieldWrap>
            <FieldWrap label="Название для сайта" level={FIELD_LEVEL.nazvanie_sayt}>
              {isEditing ? (
                <EditTextField value={m.nazvanie_sayt} onChange={(v) => setField("nazvanie_sayt", v)} />
              ) : (
                <ReadField value={m.nazvanie_sayt} />
              )}
            </FieldWrap>
          </div>
          <FieldWrap label="Описание для сайта" full level={FIELD_LEVEL.opisanie_sayt}>
            {isEditing ? (
              <textarea
                value={m.opisanie_sayt ?? ""}
                rows={4}
                onChange={(e) => setField("opisanie_sayt", e.target.value as never)}
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 resize-none"
              />
            ) : (
              <div className="px-2.5 py-1.5 text-sm text-stone-900 whitespace-pre-wrap">
                {m.opisanie_sayt || <span className="text-stone-400 italic">не задано</span>}
              </div>
            )}
          </FieldWrap>
          <FieldWrap label="Состав EN" full level={FIELD_LEVEL.composition}>
            {isEditing ? (
              <EditTextField value={m.composition} onChange={(v) => setField("composition", v)} />
            ) : (
              <ReadField value={m.composition} />
            )}
          </FieldWrap>
          <FieldWrap label="Теги" full level={FIELD_LEVEL.tegi}>
            {isEditing ? (
              <EditTextField value={m.tegi} onChange={(v) => setField("tegi", v)} />
            ) : (
              <ReadField value={m.tegi} />
            )}
          </FieldWrap>
        </div>
      </Section>
      <Section label="Ссылки на материалы" hint="Notion-карточка, стратегия, фотоконтент">
        <div className="space-y-3">
          <FieldWrap label="Notion-карточка" full level={FIELD_LEVEL.notion_link}>
            {isEditing ? (
              <EditTextField value={m.notion_link} onChange={(v) => setField("notion_link", v)} />
            ) : m.notion_link ? (
              <a
                href={m.notion_link}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-3 py-2 bg-stone-50 hover:bg-stone-100 rounded-md text-sm"
              >
                <Link2 className="w-3.5 h-3.5 text-stone-500" />
                <span className="flex-1 truncate text-stone-700">{m.notion_link}</span>
                <ExternalLink className="w-3 h-3 text-stone-400 shrink-0" />
              </a>
            ) : (
              <div className="text-sm text-stone-400 italic">Notion-карточка не задана</div>
            )}
          </FieldWrap>
          <FieldWrap label="Упаковка" full level={FIELD_LEVEL.upakovka}>
            {isEditing ? (
              <EditTextField value={m.upakovka} onChange={(v) => setField("upakovka", v)} />
            ) : (
              <ReadField value={m.upakovka} />
            )}
          </FieldWrap>
        </div>
      </Section>
    </>
  )
}

// ─── Matrix list view (Базовые модели) — Wave 2 B1 ─────────────────────────

type GroupBy = "none" | "kategoriya" | "kollekciya" | "fabrika" | "status"

const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "none", label: "Без группировки" },
  { value: "kategoriya", label: "По категории" },
  { value: "kollekciya", label: "По коллекции" },
  { value: "fabrika", label: "По фабрике" },
  { value: "status", label: "По статусу" },
]

function getGroupKey(row: MatrixRow, groupBy: GroupBy, statusNameById: Map<number, string>): string {
  switch (groupBy) {
    case "kategoriya": return row.kategoriya ?? "Без категории"
    case "kollekciya": return row.kollekciya ?? "Без коллекции"
    case "fabrika":    return row.fabrika ?? "Без фабрики"
    case "status":     return row.status_id != null
      ? (statusNameById.get(row.status_id) ?? `Статус #${row.status_id}`)
      : "Без статуса"
    default:           return ""
  }
}

interface ModeliOsnovaTableProps {
  rows: MatrixRow[]
  kategorii: { id: number; nazvanie: string }[]
  kollekcii: { id: number; nazvanie: string }[]
  modelStatuses: { id: number; nazvanie: string; tip: string; color: string | null }[]
  onOpen: (kod: string) => void
}

function ModeliOsnovaTable({ rows, kategorii, kollekcii, modelStatuses, onOpen }: ModeliOsnovaTableProps) {
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
    getUiPref<GroupBy>("matrix", "groupBy")
      .then((v) => { if (v && GROUP_BY_OPTIONS.some((o) => o.value === v)) setGroupBy(v) })
      .catch(() => { /* ignore — default is fine */ })
  }, [])

  // Persist groupBy whenever it changes
  useEffect(() => {
    if (!groupByLoadedRef.current) return
    setUiPref("matrix", "groupBy", groupBy).catch(() => { /* non-fatal */ })
  }, [groupBy])

  // Close more-menu / bulk-status dropdown when clicking elsewhere
  useEffect(() => {
    if (!openMenuKod && !bulkStatusOpen) return
    const onDocClick = () => { setOpenMenuKod(null); setBulkStatusOpen(false) }
    document.addEventListener("click", onDocClick)
    return () => document.removeEventListener("click", onDocClick)
  }, [openMenuKod, bulkStatusOpen])

  const statusNameById = useMemo(
    () => new Map(modelStatuses.map((s) => [s.id, s.nazvanie])),
    [modelStatuses],
  )

  // Status counts (from full rows, not filtered) for chip badges
  const statusCounts = useMemo(() => {
    const acc = new Map<number, number>()
    for (const r of rows) {
      if (r.status_id != null) acc.set(r.status_id, (acc.get(r.status_id) ?? 0) + 1)
    }
    return acc
  }, [rows])

  const filtered = useMemo(() => {
    let res = rows
    if (selectedStatusIds.size > 0) {
      res = res.filter((r) => r.status_id != null && selectedStatusIds.has(r.status_id))
    }
    if (selectedCategoryIds.size > 0) {
      res = res.filter((r) => r.kategoriya_id != null && selectedCategoryIds.has(r.kategoriya_id))
    }
    if (selectedCollectionNames.size > 0) {
      res = res.filter((r) => r.kollekciya != null && selectedCollectionNames.has(r.kollekciya))
    }
    if (incompleteOnly) {
      res = res.filter((r) => r.completeness < 0.5)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter((r) => {
        if (r.kod.toLowerCase().includes(q)) return true
        if ((r.nazvanie_sayt ?? "").toLowerCase().includes(q)) return true
        for (const v of r.modeli) {
          if ((v.kod ?? "").toLowerCase().includes(q)) return true
          if ((v.nazvanie ?? "").toLowerCase().includes(q)) return true
          if ((v.artikul_modeli ?? "").toLowerCase().includes(q)) return true
        }
        return false
      })
    }
    return res
  }, [rows, selectedStatusIds, selectedCategoryIds, selectedCollectionNames, incompleteOnly, search])

  // Group filtered rows
  const grouped = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "_all", label: "", items: filtered }]
    }
    const map = new Map<string, MatrixRow[]>()
    for (const r of filtered) {
      const k = getGroupKey(r, groupBy, statusNameById)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(r)
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b, "ru"))
      .map(([key, items]) => ({ key, label: key, items }))
  }, [filtered, groupBy, statusNameById])

  const toggleExpand = useCallback((id: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelect = useCallback((kod: string) => {
    setSelectedKods((prev) => {
      const next = new Set(prev)
      if (next.has(kod)) next.delete(kod)
      else next.add(kod)
      return next
    })
  }, [])

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedKods((prev) => {
      const visibleKods = filtered.map((r) => r.kod)
      const allSelected = visibleKods.length > 0 && visibleKods.every((k) => prev.has(k))
      if (allSelected) {
        const next = new Set(prev)
        for (const k of visibleKods) next.delete(k)
        return next
      }
      const next = new Set(prev)
      for (const k of visibleKods) next.add(k)
      return next
    })
  }, [filtered])

  function toggleSet<T>(set: Set<T>, value: T): Set<T> {
    const next = new Set(set)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    return next
  }

  // Bulk actions
  const handleBulkSetStatus = useCallback(async (statusId: number) => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    try {
      await bulkUpdateModelStatus(kods, statusId)
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      setSelectedKods(new Set())
      setBulkStatusOpen(false)
    } catch (err) {
      window.alert(`Не удалось обновить статус: ${(err as Error).message}`)
    }
  }, [selectedKods, queryClient])

  const handleBulkDuplicate = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    for (const srcKod of kods) {
      const newKod = window.prompt(`Дублировать «${srcKod}»: введите новый kod`, `${srcKod}_copy`)
      if (!newKod) continue
      try {
        await duplicateModel(srcKod, newKod.trim())
      } catch (err) {
        window.alert(`Не удалось дублировать ${srcKod}: ${(err as Error).message}`)
      }
    }
    await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    setSelectedKods(new Set())
  }, [selectedKods, queryClient])

  const handleBulkArchive = useCallback(async () => {
    const kods = Array.from(selectedKods)
    if (kods.length === 0) return
    const ok = window.confirm(`Архивировать ${kods.length} модель(и) и все связанные вариации/артикулы/SKU?`)
    if (!ok) return
    for (const kod of kods) {
      try {
        await archiveModel(kod)
      } catch (err) {
        window.alert(`Не удалось архивировать ${kod}: ${(err as Error).message}`)
      }
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
    } catch (err) {
      window.alert(`Не удалось дублировать: ${(err as Error).message}`)
    }
  }, [queryClient])

  const handleRowArchive = useCallback(async (kod: string) => {
    const ok = window.confirm(`Архивировать «${kod}» и все связанные вариации/артикулы/SKU?`)
    if (!ok) return
    try {
      await archiveModel(kod)
      await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    } catch (err) {
      window.alert(`Не удалось архивировать: ${(err as Error).message}`)
    }
  }, [queryClient])

  const allVisibleSelected = filtered.length > 0 && filtered.every((r) => selectedKods.has(r.kod))

  return (
    <>
      <div className="px-6 py-4 max-w-[1600px] mx-auto">
        {/* Filter bar */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Код, название, артикул вариации…"
              className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
            />
          </div>
          <button
            onClick={() => setIncompleteOnly(!incompleteOnly)}
            className={`px-2.5 py-1 text-xs rounded-md flex items-center gap-1.5 transition-colors ${
              incompleteOnly ? "bg-amber-100 text-amber-800" : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            <AlertCircle className="w-3 h-3" /> Незаполненные
          </button>
          <div className="ml-auto flex items-center gap-2">
            <label className="text-[11px] uppercase tracking-wider text-stone-500">Группировка:</label>
            <select
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value as GroupBy)}
              className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none"
            >
              {GROUP_BY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <span className="text-xs text-stone-500 tabular-nums">
              {filtered.length} из {rows.length}
            </span>
          </div>
        </div>

        {/* Category chips */}
        {kategorii.length > 0 && (
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            <span className="text-[10px] uppercase tracking-wider text-stone-400 mr-1">Категории:</span>
            {kategorii.map((k) => {
              const active = selectedCategoryIds.has(k.id)
              return (
                <button
                  key={k.id}
                  onClick={() => setSelectedCategoryIds((s) => toggleSet(s, k.id))}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                    active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 border border-stone-200"
                  }`}
                >
                  {k.nazvanie}
                </button>
              )
            })}
            {selectedCategoryIds.size > 0 && (
              <button
                onClick={() => setSelectedCategoryIds(new Set())}
                className="text-[11px] text-stone-500 hover:text-stone-800 underline ml-1"
              >
                сбросить
              </button>
            )}
          </div>
        )}

        {/* Collection chips */}
        {kollekcii.length > 0 && (
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            <span className="text-[10px] uppercase tracking-wider text-stone-400 mr-1">Коллекции:</span>
            {kollekcii.map((k) => {
              const active = selectedCollectionNames.has(k.nazvanie)
              return (
                <button
                  key={k.id}
                  onClick={() => setSelectedCollectionNames((s) => toggleSet(s, k.nazvanie))}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                    active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 border border-stone-200"
                  }`}
                >
                  {k.nazvanie}
                </button>
              )
            })}
            {selectedCollectionNames.size > 0 && (
              <button
                onClick={() => setSelectedCollectionNames(new Set())}
                className="text-[11px] text-stone-500 hover:text-stone-800 underline ml-1"
              >
                сбросить
              </button>
            )}
          </div>
        )}

        {/* Status chips with counts */}
        {modelStatuses.length > 0 && (
          <div className="flex items-center gap-1.5 mb-3 flex-wrap">
            <span className="text-[10px] uppercase tracking-wider text-stone-400 mr-1">Статусы:</span>
            {modelStatuses.map((s) => {
              const active = selectedStatusIds.has(s.id)
              const cnt = statusCounts.get(s.id) ?? 0
              return (
                <button
                  key={s.id}
                  onClick={() => setSelectedStatusIds((cur) => toggleSet(cur, s.id))}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors flex items-center gap-1.5 ${
                    active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 border border-stone-200"
                  }`}
                >
                  <span>{s.nazvanie}</span>
                  <span className={`text-[10px] tabular-nums ${active ? "text-stone-300" : "text-stone-400"}`}>
                    {cnt}
                  </span>
                </button>
              )
            })}
            {selectedStatusIds.size > 0 && (
              <button
                onClick={() => setSelectedStatusIds(new Set())}
                className="text-[11px] text-stone-500 hover:text-stone-800 underline ml-1"
              >
                сбросить
              </button>
            )}
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50/80 border-b border-stone-200">
              <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                <th className="w-8 px-2 py-2.5" />
                <th className="w-10 px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleSelectAllVisible}
                    style={{ accentColor: "#1C1917" }}
                    className="rounded border-stone-300"
                    aria-label="Выбрать все"
                  />
                </th>
                <th className="px-3 py-2.5 font-medium">Название</th>
                <th className="px-3 py-2.5 font-medium">Категория</th>
                <th className="px-3 py-2.5 font-medium">Коллекция</th>
                <th className="px-3 py-2.5 font-medium">Фабрика</th>
                <th className="px-3 py-2.5 font-medium">Статус</th>
                <th className="px-3 py-2.5 font-medium">Размеры</th>
                <th className="px-3 py-2.5 font-medium">Цвета</th>
                <th className="px-3 py-2.5 font-medium">Заполн.</th>
                <th className="px-3 py-2.5 font-medium text-right">Цв / Арт / SKU</th>
                <th className="px-3 py-2.5 font-medium">Обновлено</th>
                <th className="w-10 px-2 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {grouped.map((group) => (
                <Fragment key={`group-${group.key}`}>
                  {groupBy !== "none" && (
                    <tr className="bg-stone-100/60 border-b border-stone-200">
                      <td colSpan={13} className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-stone-800">{group.label}</span>
                          <span className="text-xs text-stone-500 tabular-nums">· {group.items.length}</span>
                        </div>
                      </td>
                    </tr>
                  )}
                  {group.items.map((m) => {
                    const canExpand = m.modeli.length >= 2
                    const isExpanded = expandedRows.has(m.id)
                    const checked = selectedKods.has(m.kod)

                    // Razmery: derive from variant rossiyskiy_razmer values that match the standard ladder.
                    const variantSizes = new Set<string>()
                    for (const v of m.modeli) {
                      const ru = (v.rossiyskiy_razmer ?? "").toUpperCase().trim()
                      if ((RAZMER_LADDER as readonly string[]).includes(ru)) variantSizes.add(ru)
                    }

                    return (
                      <Fragment key={`${m.kod}-row`}>
                        <tr className="border-b border-stone-100 hover:bg-stone-50/60 group">
                          <td className="px-2 py-3">
                            {canExpand ? (
                              <button
                                onClick={() => toggleExpand(m.id)}
                                className="p-0.5 hover:bg-stone-200 rounded"
                                aria-label={isExpanded ? "Свернуть вариации" : "Развернуть вариации"}
                              >
                                {isExpanded ? (
                                  <ChevronDown className="w-3.5 h-3.5 text-stone-500" />
                                ) : (
                                  <ChevronRight className="w-3.5 h-3.5 text-stone-500" />
                                )}
                              </button>
                            ) : (
                              <Tooltip
                                text={m.modeli.length === 1
                                  ? "У модели одна вариация — раскрытие не требуется"
                                  : "Нет вариаций"}
                              >
                                <span className="text-stone-300 text-xs">·</span>
                              </Tooltip>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleSelect(m.kod)}
                              onClick={(e) => e.stopPropagation()}
                              style={{ accentColor: "#1C1917" }}
                              className="rounded border-stone-300"
                              aria-label={`Выбрать ${m.kod}`}
                            />
                          </td>
                          <td
                            className="px-3 py-3 cursor-pointer"
                            onClick={() => onOpen(m.kod)}
                          >
                            <div className="font-medium text-stone-900 hover:underline font-mono">
                              {m.kod}
                            </div>
                            <div className="text-xs text-stone-500 truncate max-w-[220px]">
                              {m.nazvanie_sayt || (
                                <span className="italic text-stone-400">без названия</span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-3 text-stone-700">{m.kategoriya ?? "—"}</td>
                          <td className="px-3 py-3">
                            <div className="text-stone-700">{m.kollekciya ?? "—"}</div>
                            <div className="text-[11px] text-stone-400">{m.tip_kollekcii ?? ""}</div>
                          </td>
                          <td className="px-3 py-3 text-stone-700">{m.fabrika ?? "—"}</td>
                          <td className="px-3 py-3">
                            <StatusBadge statusId={m.status_id ?? 0} />
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-0.5">
                              {RAZMER_LADDER.map((sz) => {
                                const has = variantSizes.has(sz)
                                return (
                                  <span
                                    key={sz}
                                    className={`text-[10px] px-1 py-0.5 rounded ${
                                      has
                                        ? "bg-stone-900 text-white"
                                        : "bg-stone-50 text-stone-300 ring-1 ring-inset ring-stone-200"
                                    }`}
                                  >
                                    {sz}
                                  </span>
                                )
                              })}
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <ColorChips modelKod={m.kod} count={m.cveta_cnt} />
                          </td>
                          <td className="px-3 py-3">
                            <CompletenessRing value={m.completeness} size={16} hideLabel />
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-stone-600">
                            <span className="text-stone-900 font-medium">{m.cveta_cnt}</span>
                            <span className="text-stone-300 mx-1">/</span>
                            <span>{m.artikuly_cnt}</span>
                            <span className="text-stone-300 mx-1">/</span>
                            <span>{m.tovary_cnt}</span>
                          </td>
                          <td className="px-3 py-3 text-stone-500 text-xs">
                            {relativeDate(m.updated_at)}
                          </td>
                          <td className="px-2 py-3 relative">
                            <button
                              className="p-1 hover:bg-stone-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                setOpenMenuKod((cur) => (cur === m.kod ? null : m.kod))
                              }}
                              aria-label="Действия"
                            >
                              <MoreHorizontal className="w-3.5 h-3.5 text-stone-500" />
                            </button>
                            {openMenuKod === m.kod && (
                              <div
                                className="absolute right-2 top-9 z-20 w-40 bg-white border border-stone-200 rounded-md shadow-lg py-1"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <button
                                  onClick={() => { setOpenMenuKod(null); onOpen(m.kod) }}
                                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"
                                >
                                  <Edit3 className="w-3 h-3" /> Редактировать
                                </button>
                                <button
                                  onClick={() => { setOpenMenuKod(null); handleRowDuplicate(m.kod) }}
                                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"
                                >
                                  <Copy className="w-3 h-3" /> Дублировать
                                </button>
                                <button
                                  onClick={() => { setOpenMenuKod(null); handleRowArchive(m.kod) }}
                                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 text-red-600 flex items-center gap-2"
                                >
                                  <Archive className="w-3 h-3" /> Архивировать
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                        {isExpanded && (
                          <Fragment key={`${m.kod}-variations`}>
                            {m.modeli.map((v) => (
                              <tr
                                key={`v-${v.id}`}
                                className="bg-stone-50/40 border-b border-stone-100 text-xs"
                              >
                                <td colSpan={2} />
                                <td className="pl-3 py-2 pr-3">
                                  <div className="flex items-center gap-2">
                                    <div className="w-4 h-px bg-stone-300" />
                                    <span className="font-medium text-stone-800 font-mono">{v.kod}</span>
                                  </div>
                                  <div className="text-[11px] text-stone-500 ml-6 mt-0.5 truncate max-w-[200px]">
                                    {v.nazvanie}
                                  </div>
                                </td>
                                <td className="px-3 py-2 text-stone-400">—</td>
                                <td className="px-3 py-2">
                                  <div className="flex items-center gap-1 text-stone-500">
                                    <Building2 className="w-3 h-3 text-stone-400" />
                                    {v.importer_short ?? "—"}
                                  </div>
                                </td>
                                <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                                  {v.artikul_modeli ?? "—"}
                                </td>
                                <td className="px-3 py-2">
                                  <StatusBadge statusId={v.status_id ?? 0} compact />
                                </td>
                                <td className="px-3 py-2 text-stone-400 text-[10px]">
                                  RU: {v.rossiyskiy_razmer ?? "—"}
                                </td>
                                <td />
                                <td />
                                <td className="px-3 py-2 text-right tabular-nums text-stone-600">
                                  <span className="text-stone-300">—</span>
                                  <span className="text-stone-300 mx-1">/</span>
                                  <span className="text-stone-700 font-medium">{v.artikuly_cnt}</span>
                                  <span className="text-stone-300 mx-1">/</span>
                                  <span>{v.tovary_cnt}</span>
                                </td>
                                <td className="px-3 py-2 text-stone-400">—</td>
                                <td />
                              </tr>
                            ))}
                          </Fragment>
                        )}
                      </Fragment>
                    )
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-stone-500 flex items-center gap-2">
          <Info className="w-3.5 h-3.5 shrink-0" />
          <span>Стрелка ▶ раскрывает вариации. Клик по коду — карточка модели.</span>
        </div>
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

interface BulkBarProps {
  selectedCount: number
  modelStatuses: { id: number; nazvanie: string; tip: string; color: string | null }[]
  bulkStatusOpen: boolean
  onToggleBulkStatus: () => void
  onPickStatus: (id: number) => void
  onDuplicate: () => void
  onExport: () => void
  onArchive: () => void
  onClear: () => void
}

/**
 * BulkBar — обёртка над atomic BulkActionsBar с дополнительной выпадашкой
 * статусов. atomic BulkActionsBar не поддерживает submenu из коробки, поэтому
 * рисуем контейнер сами и переиспользуем стилистику.
 */
function BulkBar({
  selectedCount, modelStatuses, bulkStatusOpen, onToggleBulkStatus,
  onPickStatus, onDuplicate, onExport, onArchive, onClear,
}: BulkBarProps) {
  return (
    <div
      className="catalog-scope fixed bottom-0 left-0 right-0 z-40 border-t border-stone-200 bg-white px-6 py-3 flex items-center gap-3 shrink-0 shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.08)]"
      onClick={(e) => e.stopPropagation()}
    >
      <span className="text-sm">
        Выбрано: <span className="font-medium tabular-nums">{selectedCount}</span>
      </span>
      <div className="h-5 w-px bg-stone-200" />

      <div className="relative">
        <button
          type="button"
          onClick={onToggleBulkStatus}
          className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
        >
          Изменить статус
          <ChevronDown className="w-3 h-3" />
        </button>
        {bulkStatusOpen && (
          <div className="absolute bottom-9 left-0 z-50 w-48 bg-white border border-stone-200 rounded-md shadow-lg py-1">
            {modelStatuses.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onPickStatus(s.id)}
                className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"
              >
                <StatusBadge status={{ nazvanie: s.nazvanie, color: s.color }} compact size="sm" />
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onDuplicate}
        className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
      >
        <Copy className="w-3 h-3" /> Дублировать
      </button>

      <button
        type="button"
        onClick={onExport}
        className="px-3 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
      >
        <Download className="w-3 h-3" /> Экспорт выбранного
      </button>

      <button
        type="button"
        onClick={onArchive}
        className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md flex items-center gap-1.5"
      >
        <Archive className="w-3 h-3" /> Архивировать
      </button>

      <button
        type="button"
        onClick={onClear}
        className="ml-auto px-3 py-1 text-xs text-stone-500 hover:bg-stone-100 rounded-md"
      >
        Очистить
      </button>
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
      {Array.from({ length: visible }).map((_, i) => (
        <span
          key={i}
          className="rounded-full ring-1 ring-stone-200"
          style={{ width: 12, height: 12, background: swatchColor(`${modelKod}#${i}`) }}
        />
      ))}
      {count > 6 && (
        <span className="text-[10px] text-stone-400 ml-1 tabular-nums">+{count - 6}</span>
      )}
    </div>
  )
}

// ─── Artikuly registry tab ─────────────────────────────────────────────────

function ArtikulyTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["artikuly-registry"],
    queryFn: fetchArtikulyRegistry,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")

  const filtered = useMemo(() => {
    if (!data) return []
    if (!search.trim()) return data
    const q = search.trim().toLowerCase()
    return data.filter(
      (a) =>
        a.artikul.toLowerCase().includes(q) ||
        (a.model_osnova_kod ?? "").toLowerCase().includes(q) ||
        (a.cvet_color_code ?? "").toLowerCase().includes(q)
    )
  }, [data, search])

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  }

  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      <div className="flex items-center gap-2 mb-4">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Артикул, модель, цвет…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {data?.length ?? 0}
        </div>
      </div>
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2.5 font-medium">Артикул</th>
              <th className="px-3 py-2.5 font-medium">Модель</th>
              <th className="px-3 py-2.5 font-medium">Вариация</th>
              <th className="px-3 py-2.5 font-medium">Цвет</th>
              <th className="px-3 py-2.5 font-medium">Статус</th>
              <th className="px-3 py-2.5 font-medium">WB номенкл.</th>
              <th className="px-3 py-2.5 font-medium">OZON</th>
              <th className="px-3 py-2.5 font-medium text-right">SKU</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 100).map((a) => (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-900">{a.artikul}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{a.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{a.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={a.cvet_color_code} size={14} />
                    <span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span>
                    <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={a.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500 tabular-nums">
                  {a.nomenklatura_wb ?? "—"}
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500">
                  {a.artikul_ozon ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-stone-700">{a.tovary_cnt}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 100 && (
          <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
            Показаны первые 100 из {filtered.length}.
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Tovary registry tab ───────────────────────────────────────────────────

function TovaryTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["tovary-registry"],
    queryFn: fetchTovaryRegistry,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [channelFilter, setChannelFilter] = useState<"all" | "wb" | "ozon" | "sayt" | "lamoda">("all")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
  const [visibleCount, setVisibleCount] = useState(100)

  const productStatuses = CATALOG_STATUSES.filter((s) => s.tip === "product")

  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (channelFilter === "wb") res = res.filter((t) => t.status_id !== null)
    else if (channelFilter === "ozon") res = res.filter((t) => t.status_ozon_id !== null)
    else if (channelFilter === "sayt") res = res.filter((t) => t.status_sayt_id !== null)
    else if (channelFilter === "lamoda") res = res.filter((t) => t.status_lamoda_id !== null)
    if (statusFilter !== "all") {
      res = res.filter((t) =>
        t.status_id === statusFilter ||
        t.status_ozon_id === statusFilter ||
        t.status_sayt_id === statusFilter ||
        t.status_lamoda_id === statusFilter
      )
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter(
        (t) =>
          t.barkod.includes(q) ||
          (t.model_osnova_kod ?? "").toLowerCase().includes(q) ||
          (t.artikul ?? "").toLowerCase().includes(q)
      )
    }
    return res
  }, [data, channelFilter, statusFilter, search])

  const visible = filtered.slice(0, visibleCount)

  const CHANNELS = [
    { id: "all", label: "Все" },
    { id: "wb", label: "WB" },
    { id: "ozon", label: "Ozon" },
    { id: "sayt", label: "Сайт" },
    { id: "lamoda", label: "Lamoda" },
  ] as const

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  }

  return (
    <div className="px-6 py-4 max-w-[1600px] mx-auto">
      {/* Channel tabs */}
      <div className="flex items-center gap-1 mb-3">
        {CHANNELS.map((c) => (
          <button
            key={c.id}
            onClick={() => { setChannelFilter(c.id as typeof channelFilter); setVisibleCount(100) }}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              channelFilter === c.id
                ? "bg-stone-900 text-white"
                : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {c.label}
          </button>
        ))}
        <div className="h-4 w-px bg-stone-200 mx-1" />
        <select
          value={statusFilter === "all" ? "all" : String(statusFilter)}
          onChange={(e) => {
            setStatusFilter(e.target.value === "all" ? "all" : Number(e.target.value))
            setVisibleCount(100)
          }}
          className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none"
        >
          <option value="all">Все статусы</option>
          {productStatuses.map((s) => (
            <option key={s.id} value={s.id}>{s.nazvanie}</option>
          ))}
        </select>
      </div>

      {/* Search + count */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setVisibleCount(100) }}
            placeholder="Баркод, модель, артикул…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {data?.length ?? 0}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2.5 font-medium">Баркод</th>
              <th className="px-3 py-2.5 font-medium">Модель</th>
              <th className="px-3 py-2.5 font-medium">Вариация</th>
              <th className="px-3 py-2.5 font-medium">Цвет</th>
              <th className="px-3 py-2.5 font-medium">Размер</th>
              <th className="px-3 py-2.5 font-medium border-l border-stone-200">WB</th>
              <th className="px-3 py-2.5 font-medium">OZON</th>
              <th className="px-3 py-2.5 font-medium">Сайт</th>
              <th className="px-3 py-2.5 font-medium">Lamoda</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-700">{t.barkod}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{t.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{t.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={t.cvet_color_code} size={14} />
                    <span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5 font-mono text-xs">{t.razmer ?? "—"}</td>
                <td className="px-3 py-2.5 border-l border-stone-100">
                  <StatusBadge statusId={t.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_ozon_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_sayt_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_lamoda_id ?? 0} compact />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > visibleCount && (
          <div className="px-3 py-3 border-t border-stone-100 flex items-center justify-between">
            <span className="text-xs text-stone-400">Показано {visibleCount} из {filtered.length}</span>
            <button
              onClick={() => setVisibleCount((v) => v + 100)}
              className="text-xs text-stone-700 hover:text-stone-900 px-3 py-1 hover:bg-stone-100 rounded-md transition-colors"
            >
              Показать ещё 100
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main MatrixPage ───────────────────────────────────────────────────────

export function MatrixPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [listTab, setListTab] = useState<"modeli_osnova" | "artikuly" | "tovary">("modeli_osnova")
  const queryClient = useQueryClient()

  const modelKodParam = searchParams.get("model")
  const modelIdParam = searchParams.get("id")

  const matrixQ = useQuery({
    queryKey: ["matrix-list"],
    queryFn: fetchMatrixList,
    staleTime: 3 * 60 * 1000,
  })

  const kategoriiQ = useQuery({
    queryKey: ["kategorii"],
    queryFn: fetchKategorii,
    staleTime: 10 * 60 * 1000,
  })

  const kollekciiQ = useQuery({
    queryKey: ["kollekcii"],
    queryFn: fetchKollekcii,
    staleTime: 10 * 60 * 1000,
  })

  const statusyQ = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 30 * 60 * 1000,
  })

  // Resolve ?model=KOD → numeric id by looking up matrixQ rows.
  // Falls back to ?id=N (legacy) when present.
  const resolvedModelId: number | null = useMemo(() => {
    if (modelIdParam) {
      const n = Number(modelIdParam)
      return Number.isFinite(n) ? n : null
    }
    if (modelKodParam && matrixQ.data) {
      const row = matrixQ.data.find((r) => r.kod === modelKodParam)
      return row?.id ?? null
    }
    return null
  }, [modelIdParam, modelKodParam, matrixQ.data])

  const openModel = useCallback(
    (kod: string) => {
      const next = new URLSearchParams(searchParams)
      next.set("model", kod)
      next.delete("id")
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )
  const closeModel = useCallback(
    () => {
      const next = new URLSearchParams(searchParams)
      next.delete("model")
      next.delete("id")
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

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
    } catch (err) {
      window.alert(`Не удалось создать модель: ${(err as Error).message}`)
    }
  }, [queryClient, searchParams, setSearchParams])

  // ?model=KOD now opens B3's <ModelCardModal /> as overlay from CatalogLayout.
  // Inline `ModelCard` below is retained for reference but no longer mounted.
  void resolvedModelId
  void closeModel

  const rows = matrixQ.data ?? []
  const kategorii = kategoriiQ.data ?? []
  const kollekcii = kollekciiQ.data ?? []
  const statusy = statusyQ.data ?? []
  const modelStatuses = statusy.filter((s) => s.tip === "model")

  const totalVariations = rows.reduce((s, r) => s + r.modeli_cnt, 0)
  const totalArts = rows.reduce((s, r) => s + r.artikuly_cnt, 0)
  const totalSku = rows.reduce((s, r) => s + r.tovary_cnt, 0)

  const LIST_TABS = [
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
            <div className="text-sm text-stone-500 mt-1">
              {rows.length} моделей · {totalVariations} вариаций · {totalArts} артикулов · {totalSku} SKU
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.alert("Экспорт CSV — TODO Wave 3+")}
              className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 border border-stone-200"
            >
              <Download className="w-3.5 h-3.5" /> Экспорт
            </button>
            <button
              onClick={handleNewModel}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Новая модель
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 px-6 shrink-0">
        <div className="max-w-[1600px] mx-auto flex gap-1">
          {LIST_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setListTab(t.id as typeof listTab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                listTab === t.id
                  ? "text-stone-900 font-medium"
                  : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              {listTab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto pb-20">
        {matrixQ.isLoading && listTab === "modeli_osnova" && (
          <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
        )}
        {matrixQ.error && (
          <div className="px-6 py-8 text-sm text-red-500">
            Ошибка загрузки: {String(matrixQ.error)}
          </div>
        )}
        {listTab === "modeli_osnova" && !matrixQ.isLoading && !matrixQ.error && (
          <ModeliOsnovaTable
            rows={rows}
            kategorii={kategorii}
            kollekcii={kollekcii}
            modelStatuses={modelStatuses}
            onOpen={openModel}
          />
        )}
        {listTab === "artikuly" && <ArtikulyTable />}
        {listTab === "tovary" && <TovaryTable />}
      </div>
    </div>
  )
}
