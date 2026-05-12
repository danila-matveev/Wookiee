// Wave 2 Agent B3 — ModelCard.
//
// Карточка базовой модели. Открывается через `?model=KOD` в URL и рендерится
// поверх Matrix (B1) как modal-overlay (z-50, scroll inside).
//
// Контракт — `redesign + PIX/wookiee_matrix_mvp_v4.jsx`, компонент `ModelCard`
// (строки ~1100–1700).
//
// 5 табов: Описание, Атрибуты (по категории), Артикулы, SKU, Контент.
// editing + draft state, save через `updateModel`. Дублирование и каскадный
// архив через service.duplicateModel / service.archiveModel.

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Archive,
  Box,
  Copy,
  Edit3,
  ExternalLink,
  FileText,
  Info,
  Link2,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react"

import { supabase } from "@/lib/supabase"
import {
  ATTRIBUTES_BY_CATEGORY,
  FIELD_LEVEL,
  type AttributeFieldDef,
  type FieldLevel as FieldLevelKind,
} from "@/types/catalog"
import {
  archiveModel,
  duplicateModel,
  fetchAllTags,
  fetchFabriki,
  fetchKategorii,
  fetchKollekcii,
  fetchModelDetail,
  fetchRazmery,
  fetchSemeystvaCvetov,
  fetchSertifikaty,
  fetchStatusy,
  fetchUpakovki,
  updateModel,
  type ModelDetail,
  type ModelOsnovaPayload,
  type Sertifikat,
  type Upakovka,
} from "@/lib/catalog/service"
import {
  CompletenessRing,
  FieldWrap,
  LevelBadge,
  NumberField,
  RefModal,
  SelectField,
  StatusBadge,
  StringSelectField,
  TagsCombobox,
  TextField,
  TextareaField,
  Tooltip,
} from "@/components/catalog/ui"
import { computeCompleteness, relativeDate, swatchColor } from "@/lib/catalog/color-utils"

// ─── Local helpers ─────────────────────────────────────────────────────────

const TIPY_KOLLEKCII = [
  "commercial",
  "creative",
  "collab",
] as const

const SIZES_LINEUP = ["XS", "S", "M", "L", "XL", "XXL"] as const

/** Resolve modeli_osnova by kod → use existing id-based fetcher. */
async function fetchModelDetailByKod(kod: string): Promise<ModelDetail | null> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("id")
    .eq("kod", kod)
    .maybeSingle()
  if (error) {
    if (error.code === "PGRST116") return null
    throw error
  }
  if (!data) return null
  return fetchModelDetail((data as { id: number }).id)
}

/** Probe existence of a kod (used by Duplicate validation). */
async function probeModelKodExists(kod: string): Promise<boolean> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("id")
    .eq("kod", kod)
    .maybeSingle()
  if (error && error.code !== "PGRST116") throw error
  return Boolean(data)
}

/** Fetch hex codes for a list of cvet ids (single round-trip). */
async function fetchCvetaHex(ids: number[]): Promise<Map<number, string | null>> {
  const map = new Map<number, string | null>()
  if (ids.length === 0) return map
  const { data, error } = await supabase
    .from("cveta")
    .select("id, hex")
    .in("id", ids)
  if (error) throw error
  for (const row of (data ?? []) as { id: number; hex: string | null }[]) {
    map.set(row.id, row.hex)
  }
  return map
}

/** Junction `modeli_osnova_sertifikaty` → list of sertifikaty for a model_osnova_id. */
async function fetchModelSertifikaty(modelOsnovaId: number): Promise<Sertifikat[]> {
  const { data, error } = await supabase
    .from("modeli_osnova_sertifikaty")
    .select("sertifikaty(id, nazvanie, tip, nomer, data_vydachi, data_okonchaniya, organ_sertifikacii, file_url, gruppa_sertifikata, created_at, updated_at)")
    .eq("model_osnova_id", modelOsnovaId)
  if (error) throw error
  // Supabase types embed joins as arrays (one-to-many) even when 1:1; flatten manually.
  const rows = (data ?? []) as unknown as Array<{
    sertifikaty: Sertifikat | Sertifikat[] | null
  }>
  const out: Sertifikat[] = []
  for (const r of rows) {
    if (!r.sertifikaty) continue
    if (Array.isArray(r.sertifikaty)) out.push(...r.sertifikaty)
    else out.push(r.sertifikaty)
  }
  return out
}

async function linkSertifikatToModel(
  modelOsnovaId: number,
  sertifikatId: number,
): Promise<void> {
  const { error } = await supabase
    .from("modeli_osnova_sertifikaty")
    .upsert(
      { model_osnova_id: modelOsnovaId, sertifikat_id: sertifikatId },
      { onConflict: "model_osnova_id,sertifikat_id" },
    )
  if (error) throw new Error(error.message)
}

async function unlinkSertifikatFromModel(
  modelOsnovaId: number,
  sertifikatId: number,
): Promise<void> {
  const { error } = await supabase
    .from("modeli_osnova_sertifikaty")
    .delete()
    .eq("model_osnova_id", modelOsnovaId)
    .eq("sertifikat_id", sertifikatId)
  if (error) throw new Error(error.message)
}

/** Convert string razmery_modeli (CSV) → array of XS..XXL chips. */
function parseRazmery(raw: string | null | undefined): string[] {
  if (!raw) return []
  // accept JSON array or CSV
  const trimmed = String(raw).trim()
  if (trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) return parsed.map(String)
    } catch {
      // fall through to CSV
    }
  }
  return trimmed
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function serializeRazmery(arr: string[]): string {
  return arr.join(",")
}

// Draft type for the editing state.
type ModelDraft = ModelOsnovaPayload & {
  razmery_modeli_arr: string[]
}

function modelToDraft(m: ModelDetail): ModelDraft {
  return {
    kod: m.kod,
    kategoriya_id: m.kategoriya_id ?? null,
    kollekciya_id: m.kollekciya_id ?? null,
    fabrika_id: m.fabrika_id ?? null,
    status_id: m.status_id ?? null,
    tip_kollekcii: m.tip_kollekcii ?? null,
    material: m.material ?? null,
    sostav_syrya: m.sostav_syrya ?? null,
    composition: m.composition ?? null,
    razmery_modeli: m.razmery_modeli ?? null,
    razmery_modeli_arr: parseRazmery(m.razmery_modeli),
    sku_china: m.sku_china ?? null,
    upakovka: m.upakovka ?? null,
    upakovka_id: m.upakovka_id ?? null,
    ves_kg: m.ves_kg ?? null,
    dlina_cm: m.dlina_cm ?? null,
    shirina_cm: m.shirina_cm ?? null,
    vysota_cm: m.vysota_cm ?? null,
    kratnost_koroba: m.kratnost_koroba ?? null,
    srok_proizvodstva: m.srok_proizvodstva ?? null,
    komplektaciya: m.komplektaciya ?? null,
    nazvanie_etiketka: m.nazvanie_etiketka ?? null,
    nazvanie_sayt: m.nazvanie_sayt ?? null,
    opisanie_sayt: m.opisanie_sayt ?? null,
    details: m.details ?? null,
    description: m.description ?? null,
    tegi: m.tegi ?? null,
    notion_link: m.notion_link ?? null,
    notion_strategy_link: m.notion_strategy_link ?? null,
    yandex_disk_link: m.yandex_disk_link ?? null,
    stepen_podderzhki: m.stepen_podderzhki ?? null,
    forma_chashki: m.forma_chashki ?? null,
    regulirovka: m.regulirovka ?? null,
    zastezhka: m.zastezhka ?? null,
    dlya_kakoy_grudi: m.dlya_kakoy_grudi ?? null,
    posadka_trusov: m.posadka_trusov ?? null,
    vid_trusov: m.vid_trusov ?? null,
    naznachenie: m.naznachenie ?? null,
    stil: m.stil ?? null,
    po_nastroeniyu: m.po_nastroeniyu ?? null,
    tnved: m.tnved ?? null,
    gruppa_sertifikata: m.gruppa_sertifikata ?? null,
  }
}

/** Strip `razmery_modeli_arr` (UI-only) and serialize razmery → CSV string. */
function draftToPayload(d: ModelDraft): Partial<ModelOsnovaPayload> {
  const { razmery_modeli_arr, ...rest } = d
  return {
    ...rest,
    razmery_modeli: serializeRazmery(razmery_modeli_arr),
  }
}

// ─── UI bits (Section + SidebarBlock + Tab navigation) ─────────────────────

function Section({ label, hint, children, action }: {
  label: string
  hint?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="font-medium text-stone-900">{label}</div>
        {action}
      </div>
      {hint && <div className="text-xs text-stone-500 mb-4">{hint}</div>}
      {!hint && <div className="mb-4" />}
      {children}
    </div>
  )
}

function SidebarBlock({ title, subtitle, badge, action, children }: {
  title: string
  subtitle?: string
  badge?: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-stone-400">
          {title} {badge}
        </div>
        {action}
      </div>
      {subtitle && (
        <div className="text-[10px] text-stone-400 italic mb-2 -mt-2">
          {subtitle}
        </div>
      )}
      {children}
    </div>
  )
}

// ─── Size-lineup chip-pills (XS..XXL) ──────────────────────────────────────

function SizeLineupField({
  value, onChange, readonly, level,
}: {
  value: string[]
  onChange: (v: string[]) => void
  readonly: boolean
  level?: FieldLevelKind
}) {
  const toggle = (s: string) => {
    if (readonly) return
    if (value.includes(s)) onChange(value.filter((x) => x !== s))
    else onChange([...value, s])
  }
  return (
    <FieldWrap label="Размерная линейка" level={level} full>
      <div className="flex flex-wrap gap-1.5">
        {SIZES_LINEUP.map((s) => {
          const active = value.includes(s)
          return (
            <button
              key={s}
              type="button"
              disabled={readonly}
              onClick={() => toggle(s)}
              className={
                active
                  ? "px-3 py-1.5 text-sm rounded-full border-2 transition-colors bg-stone-900 text-white border-stone-900 font-medium tabular-nums"
                  : "px-3 py-1.5 text-sm rounded-full border-2 transition-colors bg-white text-stone-500 border-stone-200 hover:border-stone-400 tabular-nums " +
                    (readonly ? "opacity-60 cursor-default" : "")
              }
            >
              {s}
            </button>
          )
        })}
      </div>
      {!readonly && (
        <div className="text-[10px] text-stone-400 mt-2">
          Клик по чипу — включить/выключить размер.
        </div>
      )}
    </FieldWrap>
  )
}

// ─── Tab type + props passed into each tab ────────────────────────────────

type TabId = "description" | "attributes" | "articles" | "sku" | "content"

interface TabContentProps {
  m: ModelDetail
  draft: ModelDraft | null
  setDraft: (d: ModelDraft) => void
  editing: boolean
  modelOsnovaId: number
  hexByCvet: Map<number, string | null>
  /** Open a color card via ?color=KOD. */
  openColor: (colorCode: string) => void
}

// ─── Tab 1: Description ────────────────────────────────────────────────────

function TabDescription({
  m, draft, setDraft, editing,
}: TabContentProps) {
  const kategoriiQ = useQuery({
    queryKey: ["catalog", "kategorii"],
    queryFn: fetchKategorii,
    staleTime: 5 * 60 * 1000,
  })
  const kollekciiQ = useQuery({
    queryKey: ["catalog", "kollekcii"],
    queryFn: fetchKollekcii,
    staleTime: 5 * 60 * 1000,
  })
  const fabrikiQ = useQuery({
    queryKey: ["catalog", "fabriki"],
    queryFn: fetchFabriki,
    staleTime: 5 * 60 * 1000,
  })
  const statusyQ = useQuery({
    queryKey: ["catalog", "statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })
  const tagsQ = useQuery({
    queryKey: ["catalog", "tags"],
    queryFn: fetchAllTags,
    staleTime: 5 * 60 * 1000,
  })

  const set = (k: keyof ModelDraft, v: unknown) => {
    if (!draft) return
    setDraft({ ...draft, [k]: v as never })
  }

  const kategorii = kategoriiQ.data ?? []
  const kollekcii = kollekciiQ.data ?? []
  const fabriki = fabrikiQ.data ?? []
  const statusy = (statusyQ.data ?? []).filter((s) => s.tip === "model")

  // Snapshot used for read-only mode (`m` is server truth, draft mirrors it).
  const view = editing && draft ? draft : m
  const sizes = editing && draft
    ? draft.razmery_modeli_arr
    : parseRazmery(m.razmery_modeli)

  const lvl = (k: string): FieldLevelKind | undefined => FIELD_LEVEL[k]

  return (
    <>
      <Section label="Основное">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <TextField
            label="Код модели"
            value={view.kod ?? ""}
            readonly
            mono
            level={lvl("kod")}
          />
          <SelectField
            label="Статус"
            value={view.status_id ?? ""}
            options={statusy.map((s) => ({ id: s.id, nazvanie: s.nazvanie }))}
            onChange={(v) => set("status_id", v)}
            readonly={!editing}
            level={lvl("status_id")}
          />
          <SelectField
            label="Категория"
            value={view.kategoriya_id ?? ""}
            options={kategorii.map((k) => ({ id: k.id, nazvanie: k.nazvanie }))}
            onChange={(v) => set("kategoriya_id", v)}
            readonly={!editing}
            level={lvl("kategoriya_id")}
          />
          <SelectField
            label="Коллекция"
            value={view.kollekciya_id ?? ""}
            options={kollekcii.map((k) => ({ id: k.id, nazvanie: k.nazvanie }))}
            onChange={(v) => set("kollekciya_id", v)}
            readonly={!editing}
            level={lvl("kollekciya_id")}
          />
          <StringSelectField
            label="Тип коллекции"
            value={view.tip_kollekcii ?? ""}
            options={[...TIPY_KOLLEKCII]}
            onChange={(v) => set("tip_kollekcii", v)}
            readonly={!editing}
            level={lvl("tip_kollekcii")}
          />
          <SelectField
            label="Фабрика"
            value={view.fabrika_id ?? ""}
            options={fabriki.map((f) => ({ id: f.id, nazvanie: f.nazvanie }))}
            onChange={(v) => set("fabrika_id", v)}
            readonly={!editing}
            level={lvl("fabrika_id")}
          />
        </div>
      </Section>

      <Section label="Производство">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <SizeLineupField
            value={sizes}
            onChange={(v) => set("razmery_modeli_arr", v)}
            readonly={!editing}
            level={lvl("razmery_modeli")}
          />
          <TextField
            label="Материал"
            value={view.material ?? ""}
            onChange={(v) => set("material", v)}
            readonly={!editing}
            level={lvl("material")}
          />
          <TextField
            label="SKU CHINA"
            value={view.sku_china ?? ""}
            onChange={(v) => set("sku_china", v)}
            readonly={!editing}
            mono
            level={lvl("sku_china")}
          />
          <TextareaField
            label="Состав сырья"
            value={view.sostav_syrya ?? ""}
            onChange={(v) => set("sostav_syrya", v)}
            readonly={!editing}
            rows={2}
            level={lvl("sostav_syrya")}
          />
          <TextField
            label="Composition (EN)"
            value={view.composition ?? ""}
            onChange={(v) => set("composition", v)}
            readonly={!editing}
            level={lvl("composition")}
            full
          />
          <TextField
            label="Срок производства"
            value={view.srok_proizvodstva ?? ""}
            onChange={(v) => set("srok_proizvodstva", v)}
            readonly={!editing}
            level={lvl("srok_proizvodstva")}
          />
          <NumberField
            label="Кратность короба"
            value={view.kratnost_koroba ?? null}
            onChange={(v) => set("kratnost_koroba", v)}
            readonly={!editing}
            level={lvl("kratnost_koroba")}
          />
          <NumberField
            label="Вес"
            value={view.ves_kg ?? null}
            onChange={(v) => set("ves_kg", v)}
            suffix="кг"
            readonly={!editing}
            level={lvl("ves_kg")}
          />
          <NumberField
            label="Длина"
            value={view.dlina_cm ?? null}
            onChange={(v) => set("dlina_cm", v)}
            suffix="см"
            readonly={!editing}
            level={lvl("dlina_cm")}
          />
          <NumberField
            label="Ширина"
            value={view.shirina_cm ?? null}
            onChange={(v) => set("shirina_cm", v)}
            suffix="см"
            readonly={!editing}
            level={lvl("shirina_cm")}
          />
          <NumberField
            label="Высота"
            value={view.vysota_cm ?? null}
            onChange={(v) => set("vysota_cm", v)}
            suffix="см"
            readonly={!editing}
            level={lvl("vysota_cm")}
          />
        </div>
      </Section>

      <Section label="Атрибуты-отношения">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <TagsCombobox
            label="Теги"
            value={view.tegi ?? ""}
            onChange={(v) => set("tegi", v)}
            options={tagsQ.data ?? []}
            readonly={!editing}
            full
            hint="Выбери существующий тег или введи новый + Enter"
            level={lvl("tegi")}
          />
        </div>
      </Section>

      <Section label="Юридическое и сайт">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <TextField
            label="ТНВЭД"
            value={view.tnved ?? ""}
            onChange={(v) => set("tnved", v)}
            readonly={!editing}
            mono
            level={lvl("tnved")}
          />
          <TextField
            label="Группа сертификата"
            value={view.gruppa_sertifikata ?? ""}
            onChange={(v) => set("gruppa_sertifikata", v)}
            readonly={!editing}
            level={lvl("gruppa_sertifikata")}
          />
          <TextField
            label="Название этикетки"
            value={view.nazvanie_etiketka ?? ""}
            onChange={(v) => set("nazvanie_etiketka", v)}
            readonly={!editing}
            level={lvl("nazvanie_etiketka")}
          />
          <TextField
            label="Название для сайта"
            value={view.nazvanie_sayt ?? ""}
            onChange={(v) => set("nazvanie_sayt", v)}
            readonly={!editing}
            level={lvl("nazvanie_sayt")}
          />
          <TextareaField
            label="Описание для сайта"
            value={view.opisanie_sayt ?? ""}
            onChange={(v) => set("opisanie_sayt", v)}
            readonly={!editing}
            rows={4}
            level={lvl("opisanie_sayt")}
          />
          <TextareaField
            label="Details (детали)"
            value={view.details ?? ""}
            onChange={(v) => set("details", v)}
            readonly={!editing}
            rows={3}
            level="model"
          />
          <TextareaField
            label="Description"
            value={view.description ?? ""}
            onChange={(v) => set("description", v)}
            readonly={!editing}
            rows={3}
            level="model"
          />
        </div>
      </Section>
    </>
  )
}

// ─── Tab 2: Attributes (dynamic per category) ──────────────────────────────

function TabAttributes({ m, draft, setDraft, editing }: TabContentProps) {
  const attrs: AttributeFieldDef[] = m.kategoriya_id
    ? ATTRIBUTES_BY_CATEGORY[m.kategoriya_id] ?? []
    : []

  const set = (k: string, v: unknown) => {
    if (!draft) return
    setDraft({ ...draft, [k]: v as never })
  }
  const view = (editing && draft
    ? (draft as unknown as Record<string, unknown>)
    : (m as unknown as Record<string, unknown>))

  if (attrs.length === 0) {
    return (
      <Section label="Атрибуты">
        <div className="text-sm text-stone-400 italic">
          Нет специфичных атрибутов для этой категории
        </div>
      </Section>
    )
  }

  return (
    <Section
      label={`Атрибуты категории «${m.kategoriya ?? "—"}»`}
      hint={`${attrs.length} атрибутов настроены для этой категории`}
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-4">
        {attrs.map((a) => {
          const lvl = FIELD_LEVEL[a.key] ?? "model"
          if (a.type === "select" && a.options) {
            return (
              <StringSelectField
                key={a.key}
                label={a.label}
                value={(view[a.key] as string | null) ?? ""}
                options={a.options}
                onChange={(v) => set(a.key, v)}
                readonly={!editing}
                level={lvl}
              />
            )
          }
          return (
            <TextField
              key={a.key}
              label={a.label}
              value={(view[a.key] as string | null) ?? ""}
              onChange={(v) => set(a.key, v)}
              readonly={!editing}
              level={lvl}
            />
          )
        })}
      </div>
    </Section>
  )
}

// ─── Tab 3: Articles ───────────────────────────────────────────────────────

function TabArticles({ m, hexByCvet, openColor }: TabContentProps) {
  const allArts = m.modeli.flatMap((v) =>
    v.artikuly.map((a) => ({ ...a, variantKod: v.kod, importerName: v.importer_nazvanie })),
  )
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
        <div>
          <div className="font-medium text-stone-900">Артикулы модели</div>
          <div className="text-xs text-stone-500">
            {allArts.length} артикулов · клик по цвету — карточка цвета
          </div>
        </div>
        <button
          type="button"
          className="px-2.5 py-1 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          disabled
          title="Wave 3+ (Add артикула)"
        >
          <Plus className="w-3 h-3" /> Добавить
        </button>
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
          {allArts.map((a) => {
            const hex = a.cvet_id != null ? hexByCvet.get(a.cvet_id) ?? null : null
            const swatch = hex ?? (a.cvet_color_code ? swatchColor(a.cvet_color_code) : "#E7E5E4")
            return (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-700">{a.artikul}</td>
                <td className="px-3 py-2 font-mono text-xs text-stone-600">{a.variantKod}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => a.cvet_color_code && openColor(a.cvet_color_code)}
                    disabled={!a.cvet_color_code}
                    className="flex items-center gap-1.5 hover:bg-stone-100 rounded px-1 py-0.5 -mx-1 disabled:cursor-default"
                  >
                    <span
                      className="inline-block w-3.5 h-3.5 rounded ring-1 ring-stone-200 shrink-0"
                      style={{ background: swatch }}
                    />
                    <span className="font-mono text-xs text-stone-700">
                      {a.cvet_color_code ?? "—"}
                    </span>
                    {a.cvet_nazvanie && (
                      <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>
                    )}
                  </button>
                </td>
                <td className="px-3 py-2"><StatusBadge statusId={a.status_id ?? 0} compact /></td>
                <td className="px-3 py-2 font-mono text-[11px] text-stone-500 tabular-nums">
                  {a.nomenklatura_wb ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                  {a.artikul_ozon ?? "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-stone-700">
                  {a.tovary.length}
                </td>
              </tr>
            )
          })}
          {allArts.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-8 text-center text-sm text-stone-400 italic">
                У модели нет артикулов
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── Tab 4: SKU ────────────────────────────────────────────────────────────

function TabSKU({ m, hexByCvet }: TabContentProps) {
  const allSku = m.modeli.flatMap((v) =>
    v.artikuly.flatMap((a) =>
      a.tovary.map((t) => ({
        ...t,
        variantKod: v.kod,
        cvet_color_code: a.cvet_color_code,
        cvet_id: a.cvet_id,
      })),
    ),
  )

  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200">
        <div className="font-medium text-stone-900">SKU модели</div>
        <div className="text-xs text-stone-500">
          {allSku.length} SKU · inline-edit статусов — Wave 3+ (TODO)
        </div>
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
            {allSku.slice(0, 100).map((t) => {
              const hex = t.cvet_id != null ? hexByCvet.get(t.cvet_id) ?? null : null
              const swatch = hex ?? (t.cvet_color_code ? swatchColor(t.cvet_color_code) : "#E7E5E4")
              return (
                <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                  <td className="px-3 py-2 font-mono text-xs text-stone-700">{t.barkod}</td>
                  <td className="px-3 py-2 font-mono text-xs text-stone-600">{t.variantKod}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="inline-block w-3.5 h-3.5 rounded ring-1 ring-stone-200 shrink-0"
                        style={{ background: swatch }}
                      />
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
              )
            })}
            {allSku.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-sm text-stone-400 italic">
                  Нет SKU для этой модели
                </td>
              </tr>
            )}
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

// ─── Tab 5: Content (links + Упаковка + Сертификаты) ───────────────────────

function TabContent({ m, draft, setDraft, editing, modelOsnovaId }: TabContentProps) {
  const upakovkiQ = useQuery({
    queryKey: ["catalog", "upakovki"],
    queryFn: fetchUpakovki,
    staleTime: 5 * 60 * 1000,
  })
  const sertifikatyQ = useQuery({
    queryKey: ["catalog", "sertifikaty"],
    queryFn: fetchSertifikaty,
    staleTime: 5 * 60 * 1000,
  })
  const modelSertsQ = useQuery({
    queryKey: ["catalog", "model-sertifikaty", modelOsnovaId],
    queryFn: () => fetchModelSertifikaty(modelOsnovaId),
    staleTime: 60 * 1000,
  })
  const queryClient = useQueryClient()

  const [pickingSert, setPickingSert] = useState(false)

  const linkMut = useMutation({
    mutationFn: (sertifikatId: number) => linkSertifikatToModel(modelOsnovaId, sertifikatId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", "model-sertifikaty", modelOsnovaId],
      })
    },
  })
  const unlinkMut = useMutation({
    mutationFn: (sertifikatId: number) => unlinkSertifikatFromModel(modelOsnovaId, sertifikatId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", "model-sertifikaty", modelOsnovaId],
      })
    },
  })

  const set = (k: keyof ModelDraft, v: unknown) => {
    if (!draft) return
    setDraft({ ...draft, [k]: v as never })
  }
  const view = editing && draft ? draft : m
  const upakovki: Upakovka[] = upakovkiQ.data ?? []
  const sertifikaty: Sertifikat[] = sertifikatyQ.data ?? []
  const modelSerts: Sertifikat[] = modelSertsQ.data ?? []

  const upak = view.upakovka_id
    ? upakovki.find((u) => u.id === view.upakovka_id) ?? null
    : null

  // Sertifikat options (filtered: not yet linked)
  const linkedIds = new Set(modelSerts.map((s) => s.id))
  const availableSerts = sertifikaty.filter((s) => !linkedIds.has(s.id))

  return (
    <>
      <Section label="Ссылки на материалы" hint="Notion-карточка, продуктовая стратегия, фото-папка">
        <div className="space-y-3">
          {/* notion_link */}
          <FieldWrap label="Notion · карточка модели" level="model" full>
            {!editing ? (
              view.notion_link ? (
                <a
                  href={view.notion_link}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2.5 py-1.5 text-sm text-stone-700 hover:text-stone-900 inline-flex items-center gap-1.5 bg-stone-50 hover:bg-stone-100 rounded-md w-full"
                >
                  <Link2 className="w-3.5 h-3.5" />
                  <span className="truncate flex-1">{view.notion_link}</span>
                  <ExternalLink className="w-3 h-3 ml-auto shrink-0" />
                </a>
              ) : (
                <div className="text-sm text-stone-400 italic">не задано</div>
              )
            ) : (
              <input
                type="url"
                value={view.notion_link ?? ""}
                onChange={(e) => set("notion_link", e.target.value)}
                placeholder="https://notion.so/..."
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              />
            )}
          </FieldWrap>

          {/* notion_strategy_link */}
          <FieldWrap
            label="Notion · продуктовая стратегия"
            level="model"
            full
            hint="Стратегия позиционирования, конкуренты, гипотезы"
          >
            {!editing ? (
              view.notion_strategy_link ? (
                <a
                  href={view.notion_strategy_link}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2.5 py-1.5 text-sm text-stone-700 hover:text-stone-900 inline-flex items-center gap-1.5 bg-stone-50 hover:bg-stone-100 rounded-md w-full"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span className="truncate flex-1">{view.notion_strategy_link}</span>
                  <ExternalLink className="w-3 h-3 ml-auto shrink-0" />
                </a>
              ) : (
                <div className="text-sm text-stone-400 italic">не задано</div>
              )
            ) : (
              <input
                type="url"
                value={view.notion_strategy_link ?? ""}
                onChange={(e) => set("notion_strategy_link", e.target.value)}
                placeholder="https://notion.so/..."
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              />
            )}
          </FieldWrap>

          {/* yandex_disk_link */}
          <FieldWrap
            label="Яндекс.Диск · фотоконтент"
            level="model"
            full
            hint="Папка с фотографиями товара для сайта и МП"
          >
            {!editing ? (
              view.yandex_disk_link ? (
                <a
                  href={view.yandex_disk_link}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2.5 py-1.5 text-sm text-stone-700 hover:text-stone-900 inline-flex items-center gap-1.5 bg-stone-50 hover:bg-stone-100 rounded-md w-full"
                >
                  <Box className="w-3.5 h-3.5" />
                  <span className="truncate flex-1">{view.yandex_disk_link}</span>
                  <ExternalLink className="w-3 h-3 ml-auto shrink-0" />
                </a>
              ) : (
                <div className="text-sm text-stone-400 italic">не задано</div>
              )
            ) : (
              <input
                type="url"
                value={view.yandex_disk_link ?? ""}
                onChange={(e) => set("yandex_disk_link", e.target.value)}
                placeholder="https://disk.yandex.ru/d/..."
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              />
            )}
          </FieldWrap>
        </div>
      </Section>

      <Section
        label="Упаковка"
        hint="Выбор из справочника упаковок. Габариты подтянутся автоматически."
      >
        {editing ? (
          <select
            value={view.upakovka_id ?? ""}
            onChange={(e) =>
              set("upakovka_id", e.target.value === "" ? null : Number(e.target.value))
            }
            className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
          >
            <option value="">— Не выбрано</option>
            {upakovki.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nazvanie}
                {u.dlina_cm
                  ? ` (${u.dlina_cm}×${u.shirina_cm}×${u.vysota_cm} см)`
                  : ""}
              </option>
            ))}
          </select>
        ) : upak ? (
          <div className="flex items-start justify-between p-3 bg-stone-50 rounded-md">
            <div>
              <div className="font-medium text-stone-900 flex items-center gap-2">
                <Box className="w-3.5 h-3.5 text-stone-500" /> {upak.nazvanie}
              </div>
              <div className="text-xs text-stone-500 mt-1 space-x-1">
                {upak.dlina_cm != null && (
                  <span>
                    Габариты:{" "}
                    <span className="font-mono">
                      {upak.dlina_cm}×{upak.shirina_cm}×{upak.vysota_cm} см
                    </span>{" "}
                    ·
                  </span>
                )}
                {upak.obem_l != null && (
                  <span>
                    Объём: <span className="font-mono">{upak.obem_l} л</span> ·
                  </span>
                )}
                {upak.price_yuan != null && upak.price_yuan > 0 && (
                  <span>
                    Цена: <span className="font-mono">{upak.price_yuan} ¥</span> ·
                  </span>
                )}
                <span>Срок: {upak.srok_izgotovleniya_dni ?? "—"}</span>
              </div>
              {upak.notes && (
                <div className="text-xs text-stone-400 italic mt-1">{upak.notes}</div>
              )}
            </div>
            {upak.file_link && (
              <a
                href={upak.file_link}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-stone-500 hover:text-stone-900 flex items-center gap-1 shrink-0"
              >
                <ExternalLink className="w-3 h-3" /> Файл
              </a>
            )}
          </div>
        ) : (
          <div className="text-sm text-stone-400 italic">Упаковка не выбрана</div>
        )}
      </Section>

      <Section
        label="Сертификаты"
        hint={`${modelSerts.length} сертификатов привязано к модели`}
        action={
          <button
            type="button"
            onClick={() => setPickingSert(true)}
            className="px-2.5 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
          >
            <Plus className="w-3 h-3" /> Сертификат
          </button>
        }
      >
        {modelSertsQ.isLoading ? (
          <div className="text-sm text-stone-400 italic">Загрузка…</div>
        ) : modelSerts.length === 0 ? (
          <div className="text-sm text-stone-400 italic">
            К модели не привязано ни одного сертификата
          </div>
        ) : (
          <div className="space-y-2">
            {modelSerts.map((s) => (
              <div
                key={s.id}
                className="flex items-start justify-between p-3 bg-stone-50 rounded-md"
              >
                <div>
                  <div className="font-medium text-stone-900">{s.nazvanie}</div>
                  <div className="text-xs text-stone-500 mt-0.5 space-x-1">
                    {s.tip && <span>{s.tip} ·</span>}
                    {s.nomer && <span>№ {s.nomer} ·</span>}
                    {s.data_okonchaniya && <span>до {s.data_okonchaniya}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {s.file_url && (
                    <a
                      href={s.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-stone-500 hover:text-stone-900 flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" /> Файл
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => unlinkMut.mutate(s.id)}
                    className="p-1 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded"
                    aria-label="Отвязать"
                    title="Отвязать"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {pickingSert && (
        sertifikatyQ.isLoading || availableSerts.length === 0 ? (
          <SertPickerEmptyModal
            loading={sertifikatyQ.isLoading}
            onCancel={() => setPickingSert(false)}
          />
        ) : (
          <RefModal
            title="Привязать сертификат"
            fields={[
              {
                key: "sertifikat_id",
                label: "Сертификат",
                type: "select",
                required: true,
                options: availableSerts.map((s) => ({
                  value: s.id,
                  label: `${s.nazvanie}${s.nomer ? " · № " + s.nomer : ""}`,
                })),
                full: true,
              },
            ]}
            onSave={async (vals) => {
              const id = Number(vals.sertifikat_id)
              if (!Number.isFinite(id)) return
              await linkMut.mutateAsync(id)
              setPickingSert(false)
            }}
            onCancel={() => setPickingSert(false)}
            saveLabel="Привязать"
          />
        )
      )}
    </>
  )
}

// ─── Empty/loading cert-picker modal (W1.7) ────────────────────────────────
//
// RefModal не поддерживает кастомный footer / disabled submit без значения,
// поэтому при пустом списке (нет ни одного сертификата в БД или все уже
// привязаны) показываем отдельную лёгкую модалку: сообщение + ссылка на
// справочник сертификатов + disabled-кнопка «Привязать».
function SertPickerEmptyModal({
  loading, onCancel,
}: {
  loading: boolean
  onCancel: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onCancel])

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <h2
            className="cat-font-serif text-xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            Привязать сертификат
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="p-1 hover:bg-stone-100 rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-6 space-y-3">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">
              Сертификат
            </label>
            <div className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-stone-50 text-stone-400 italic">
              {loading ? "Загрузка…" : "Нет доступных сертификатов"}
            </div>
          </div>
          {!loading && (
            <Link
              to="/catalog/sertifikaty"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm text-stone-700 hover:text-stone-900 underline underline-offset-2"
            >
              Создать сертификат
              <ExternalLink className="w-3 h-3" />
            </Link>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            type="button"
            disabled
            className="px-3 py-1.5 text-sm text-white bg-stone-900 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Привязать
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Sidebar ───────────────────────────────────────────────────────────────

function CardSidebar({
  m, attrs, hexByCvet, openColor,
}: {
  m: ModelDetail
  attrs: AttributeFieldDef[]
  hexByCvet: Map<number, string | null>
  openColor: (colorCode: string) => void
}) {
  // Ring % and "X/Y" text must agree — both reflect category-specific
  // attribute fill ratio. Earlier the ring used `computeCompleteness` (weighted
  // across all model fields) while the text counted only AttributeFieldDef
  // entries, which produced 70% ring vs "10/10" text.
  void computeCompleteness
  const attrFilled = attrs.filter(
    (a) => Boolean((m as unknown as Record<string, unknown>)[a.key]),
  ).length
  const completeness = attrs.length > 0 ? attrFilled / attrs.length : 0

  // Unique cveta in model.
  const cvetaList = useMemo(() => {
    const seen = new Map<string, { code: string; name: string | null; cvetId: number | null }>()
    for (const v of m.modeli) {
      for (const a of v.artikuly) {
        if (!a.cvet_color_code) continue
        if (!seen.has(a.cvet_color_code)) {
          seen.set(a.cvet_color_code, {
            code: a.cvet_color_code,
            name: a.cvet_nazvanie,
            cvetId: a.cvet_id,
          })
        }
      }
    }
    return [...seen.values()]
  }, [m])

  return (
    <>
      <SidebarBlock title="Заполненность">
        <div className="flex items-center gap-3">
          <CompletenessRing value={completeness} size={56} hideLabel />
          <div className="flex-1">
            <div className="text-2xl font-medium tabular-nums text-stone-900">
              {Math.round(completeness * 100)}%
            </div>
            <div className="text-xs text-stone-500">
              Атрибутов: {attrFilled}/{attrs.length}
            </div>
          </div>
        </div>
      </SidebarBlock>

      <SidebarBlock
        title="Метрики"
        subtitle="placeholder для остатков, оборачиваемости (Wave 3+)"
      >
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between text-stone-400">
            <span>Остаток на складе</span>
            <span className="tabular-nums">— шт</span>
          </div>
          <div className="flex justify-between text-stone-400">
            <span>Оборачиваемость</span>
            <span className="tabular-nums">— дн</span>
          </div>
          <div className="flex justify-between text-stone-400">
            <span>Продаж за 30 дн</span>
            <span className="tabular-nums">— шт</span>
          </div>
          <div className="text-[10px] text-stone-400 italic mt-2 pt-2 border-t border-stone-100">
            Обновлено: {relativeDate(m.updated_at)}
          </div>
        </div>
      </SidebarBlock>

      <SidebarBlock
        title="Вариации"
        badge={
          <Tooltip text="Вариация = базовая модель × юрлицо. Например, Vuki может выпускаться через ИП и через ООО — это две вариации.">
            <Info className="w-3 h-3 text-stone-400" />
          </Tooltip>
        }
        action={
          <button
            type="button"
            disabled
            className="text-xs text-stone-700 hover:bg-stone-100 rounded px-2 py-0.5 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Wave 3+ (создание вариации)"
          >
            <Plus className="w-3 h-3" /> Добавить
          </button>
        }
      >
        <div className="space-y-1">
          {m.modeli.length > 0 ? (
            m.modeli.map((v) => (
              <Tooltip
                key={v.id}
                text={`${v.nazvanie}${v.importer_nazvanie ? " · " + v.importer_nazvanie : ""}`}
              >
                <div className="flex items-center justify-between py-1.5 px-2 -mx-2 hover:bg-stone-50 rounded text-sm">
                  <span className="font-mono text-stone-900">{v.kod}</span>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">
                    {v.importer_nazvanie?.split(" ")[0] ?? "—"}
                  </span>
                </div>
              </Tooltip>
            ))
          ) : (
            <div className="text-sm text-stone-400 italic">Нет вариаций</div>
          )}
        </div>
      </SidebarBlock>

      <SidebarBlock
        title="Цвета модели"
        badge={
          <span className="text-xs text-stone-500 tabular-nums">{cvetaList.length}</span>
        }
      >
        <div className="flex flex-wrap gap-1.5">
          {cvetaList.slice(0, 24).map((c) => {
            const hex = c.cvetId != null ? hexByCvet.get(c.cvetId) ?? null : null
            const swatch = hex ?? swatchColor(c.code)
            return (
              <Tooltip key={c.code} text={c.name ? `${c.name} (${c.code})` : c.code}>
                <button
                  type="button"
                  onClick={() => openColor(c.code)}
                  className="flex items-center gap-1.5 bg-stone-50 hover:bg-stone-100 rounded px-1.5 py-1 text-xs"
                >
                  <span
                    className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
                    style={{ background: swatch }}
                  />
                  <span className="font-mono text-[10px] text-stone-700">{c.code}</span>
                </button>
              </Tooltip>
            )
          })}
          {cvetaList.length > 24 && (
            <span className="text-xs text-stone-400 self-center">
              +{cvetaList.length - 24}
            </span>
          )}
          {cvetaList.length === 0 && (
            <span className="text-xs text-stone-400 italic">Нет цветов</span>
          )}
        </div>
      </SidebarBlock>
    </>
  )
}

// ─── Header (icon + kod + buttons) ─────────────────────────────────────────

interface HeaderProps {
  m: ModelDetail
  hexByCvet: Map<number, string | null>
  editing: boolean
  setEditing: (v: boolean) => void
  resetDraft: () => void
  onSave: () => void
  saving: boolean
  onDuplicate: () => void
  onArchive: () => void
  onClose: () => void
}

function Header({
  m, hexByCvet, editing, setEditing, resetDraft, onSave, saving,
  onDuplicate, onArchive, onClose,
}: HeaderProps) {
  // Big swatch from first cvet.
  const firstCvet = useMemo(() => {
    for (const v of m.modeli) {
      for (const a of v.artikuly) {
        if (a.cvet_color_code) return { code: a.cvet_color_code, id: a.cvet_id }
      }
    }
    return null
  }, [m])

  const headerImageUrl = (m as { header_image_url?: string | null }).header_image_url ?? null
  const swatch = firstCvet
    ? (firstCvet.id != null ? hexByCvet.get(firstCvet.id) ?? null : null)
      ?? swatchColor(firstCvet.code)
    : "#E7E5E4"

  return (
    <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4 flex items-center gap-4">
      {/* Icon */}
      <div
        className="w-14 h-14 rounded-lg ring-1 ring-stone-200 shrink-0 overflow-hidden flex items-center justify-center bg-stone-50"
        style={!headerImageUrl ? { background: swatch } : undefined}
      >
        {headerImageUrl ? (
          <img src={headerImageUrl} alt="" className="w-full h-full object-cover" />
        ) : firstCvet ? null : (
          <Box className="w-6 h-6 text-stone-400" />
        )}
      </div>

      {/* Title */}
      <div className="flex-1 min-w-0">
        <div className="text-xs text-stone-400 mb-0.5">
          Базовая модель · {m.kategoriya ?? "—"}
        </div>
        <div className="flex items-center gap-3">
          <h1
            className="cat-font-serif italic text-stone-900"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif", fontSize: 32, lineHeight: 1.1 }}
          >
            {m.kod}
          </h1>
          <StatusBadge statusId={m.status_id ?? 0} />
          <span className="text-sm text-stone-400">·</span>
          <span className="text-sm text-stone-500 truncate">
            {m.nazvanie_etiketka || m.nazvanie_sayt || "без названия"}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {editing ? (
          <>
            <button
              type="button"
              onClick={() => {
                resetDraft()
                setEditing(false)
              }}
              className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-md"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5 disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? "Сохраняем…" : "Сохранить"}
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={onDuplicate}
              className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
            >
              <Copy className="w-3.5 h-3.5" /> Дублировать
            </button>
            <button
              type="button"
              onClick={onArchive}
              className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
            >
              <Archive className="w-3.5 h-3.5" /> В архив
            </button>
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
            >
              <Edit3 className="w-3.5 h-3.5" /> Редактировать
            </button>
            <div className="h-6 w-px bg-stone-200 mx-1" />
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 hover:bg-stone-100 rounded-md"
              aria-label="Close"
            >
              <X className="w-4 h-4 text-stone-700" />
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main ModelCard component ──────────────────────────────────────────────

interface ModelCardProps {
  kod: string
  onClose: () => void
}

export function ModelCard({ kod, onClose }: ModelCardProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const tab = (searchParams.get("tab") as TabId | null) ?? "description"
  const setTab = useCallback(
    (next: TabId) => {
      const sp = new URLSearchParams(searchParams)
      sp.set("model", kod)
      sp.set("tab", next)
      setSearchParams(sp, { replace: true })
    },
    [kod, searchParams, setSearchParams],
  )

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<ModelDraft | null>(null)
  const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)

  // Fetch model detail.
  const { data: model, isLoading, error } = useQuery({
    queryKey: ["catalog", "model", kod],
    queryFn: () => fetchModelDetailByKod(kod),
    staleTime: 60 * 1000,
  })

  // Razmery select reference (we only need it to inform the chip lineup).
  // Currently chip-pills use the constant SIZES_LINEUP — no DB read needed.
  // razmery query is kept here for future use (TODO Wave 3+).
  useQuery({
    queryKey: ["catalog", "razmery"],
    queryFn: fetchRazmery,
    staleTime: 5 * 60 * 1000,
  })
  // Likewise SemeystvaCvetov — used by Color tabs eventually.
  useQuery({
    queryKey: ["catalog", "semeystva-cvetov"],
    queryFn: fetchSemeystvaCvetov,
    staleTime: 5 * 60 * 1000,
  })

  // Resync draft when entering/leaving editing or when model changes.
  useEffect(() => {
    if (!editing) {
      setDraft(null)
    } else if (model) {
      setDraft(modelToDraft(model))
    }
  }, [editing, model])

  // Reset editing when changing kod.
  useEffect(() => {
    setEditing(false)
  }, [kod])

  // Fetch hex codes for cveta in this model in one shot (parallel to detail).
  const cvetIds = useMemo(() => {
    if (!model) return [] as number[]
    const set = new Set<number>()
    for (const v of model.modeli) {
      for (const a of v.artikuly) {
        if (a.cvet_id != null) set.add(a.cvet_id)
      }
    }
    return [...set]
  }, [model])

  const hexQ = useQuery({
    queryKey: ["catalog", "cveta-hex", cvetIds.sort((a, b) => a - b).join(",")],
    queryFn: () => fetchCvetaHex(cvetIds),
    enabled: cvetIds.length > 0,
    staleTime: 5 * 60 * 1000,
  })
  const hexByCvet = hexQ.data ?? new Map<number, string | null>()

  // Save mutation
  const saveMut = useMutation({
    mutationFn: async () => {
      if (!draft) return
      await updateModel(kod, draftToPayload(draft))
    },
    onSuccess: () => {
      setEditing(false)
      setDraft(null)
      queryClient.invalidateQueries({ queryKey: ["catalog", "model", kod] })
      queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    },
  })

  // Duplicate
  const duplicateMut = useMutation({
    mutationFn: async (newKod: string) => {
      const exists = await probeModelKodExists(newKod)
      if (exists) throw new Error(`Модель с kod «${newKod}» уже существует`)
      return duplicateModel(kod, newKod)
    },
    onSuccess: (newKod) => {
      setDuplicateOpen(false)
      queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      const sp = new URLSearchParams(searchParams)
      sp.set("model", newKod)
      sp.delete("tab")
      setSearchParams(sp, { replace: true })
    },
  })

  // Archive
  const archiveMut = useMutation({
    mutationFn: () => archiveModel(kod),
    onSuccess: () => {
      setArchiveOpen(false)
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ["catalog", "model", kod] })
      queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    },
  })

  const openColor = useCallback(
    (code: string) => {
      const sp = new URLSearchParams(searchParams)
      sp.delete("model")
      sp.delete("tab")
      sp.set("color", code)
      setSearchParams(sp, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  // Render container (modal-overlay).
  return (
    <div className="fixed inset-0 z-50 bg-stone-900/30 flex">
      <div
        className="absolute inset-0"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative ml-auto w-full max-w-[min(1280px,98vw)] h-full bg-stone-50 border-l border-stone-200 shadow-2xl flex flex-col overflow-hidden">
        {isLoading && (
          <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
            Загрузка модели…
          </div>
        )}
        {error && (
          <div className="flex-1 flex items-center justify-center text-red-500 text-sm">
            Ошибка загрузки: {String(error)}
          </div>
        )}
        {!isLoading && !error && !model && (
          <div className="flex-1 flex items-center justify-center text-stone-500 text-sm">
            Модель «{kod}» не найдена.
          </div>
        )}
        {model && (
          <>
            <Header
              m={model}
              hexByCvet={hexByCvet}
              editing={editing}
              setEditing={setEditing}
              resetDraft={() => setDraft(null)}
              onSave={() => saveMut.mutate()}
              saving={saveMut.isPending}
              onDuplicate={() => setDuplicateOpen(true)}
              onArchive={() => setArchiveOpen(true)}
              onClose={onClose}
            />

            {/* Tab bar */}
            <div className="border-b border-stone-200 bg-white px-6 flex gap-1 shrink-0">
              {([
                { id: "description", label: "Описание" },
                { id: "attributes", label: "Атрибуты" },
                { id: "articles", label: "Артикулы", count: model.modeli.flatMap((v) => v.artikuly).length },
                {
                  id: "sku",
                  label: "SKU",
                  count: model.modeli.flatMap((v) => v.artikuly.flatMap((a) => a.tovary)).length,
                },
                { id: "content", label: "Контент" },
              ] as Array<{ id: TabId; label: string; count?: number }>).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={
                    "relative px-3 py-2.5 text-sm transition-colors " +
                    (tab === t.id
                      ? "text-stone-900 font-medium"
                      : "text-stone-500 hover:text-stone-800")
                  }
                >
                  {t.label}
                  {t.count != null && (
                    <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">
                      {t.count}
                    </span>
                  )}
                  {tab === t.id && (
                    <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />
                  )}
                </button>
              ))}
            </div>

            {saveMut.error && (
              <div className="px-6 py-2 text-xs text-red-700 bg-red-50 border-b border-red-100">
                Ошибка сохранения: {String(saveMut.error)}
              </div>
            )}
            {duplicateMut.error && (
              <div className="px-6 py-2 text-xs text-red-700 bg-red-50 border-b border-red-100">
                {String(duplicateMut.error instanceof Error
                  ? duplicateMut.error.message
                  : duplicateMut.error)}
              </div>
            )}
            {archiveMut.error && (
              <div className="px-6 py-2 text-xs text-red-700 bg-red-50 border-b border-red-100">
                Ошибка архивирования: {String(archiveMut.error)}
              </div>
            )}

            {/* Body */}
            <div className="flex-1 overflow-y-auto">
              <div className="grid grid-cols-[2fr_1fr] gap-6 p-6 max-w-[1280px] mx-auto w-full">
                <div className="space-y-3 min-w-0">
                  <TabSwitcher
                    tab={tab}
                    m={model}
                    draft={draft}
                    setDraft={setDraft}
                    editing={editing}
                    modelOsnovaId={model.id}
                    hexByCvet={hexByCvet}
                    openColor={openColor}
                  />
                </div>
                <div className="space-y-4 min-w-0">
                  <CardSidebar
                    m={model}
                    attrs={
                      model.kategoriya_id
                        ? ATTRIBUTES_BY_CATEGORY[model.kategoriya_id] ?? []
                        : []
                    }
                    hexByCvet={hexByCvet}
                    openColor={openColor}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {duplicateOpen && (
        <DuplicateModal
          srcKod={kod}
          onCancel={() => setDuplicateOpen(false)}
          onConfirm={(newKod) => duplicateMut.mutate(newKod)}
          pending={duplicateMut.isPending}
        />
      )}
      {archiveOpen && (
        <ArchiveModal
          kod={kod}
          onCancel={() => setArchiveOpen(false)}
          onConfirm={() => archiveMut.mutate()}
          pending={archiveMut.isPending}
        />
      )}
    </div>
  )
}

// ─── Switcher (so each tab can call hooks safely with Hook rules) ──────────

function TabSwitcher(props: TabContentProps & { tab: TabId }) {
  const { tab, ...rest } = props
  switch (tab) {
    case "description": return <TabDescription {...rest} />
    case "attributes":  return <TabAttributes  {...rest} />
    case "articles":    return <TabArticles    {...rest} />
    case "sku":         return <TabSKU         {...rest} />
    case "content":     return <TabContent     {...rest} />
    default:            return null
  }
}

// ─── Duplicate / Archive sub-modals ────────────────────────────────────────

function DuplicateModal({
  srcKod, onCancel, onConfirm, pending,
}: {
  srcKod: string
  onCancel: () => void
  onConfirm: (newKod: string) => void
  pending: boolean
}) {
  const [kod, setKod] = useState("")
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    const trimmed = kod.trim()
    if (!trimmed) {
      setError("Введите код новой модели")
      return
    }
    if (trimmed === srcKod) {
      setError("Новый kod должен отличаться от исходного")
      return
    }
    setError(null)
    onConfirm(trimmed)
  }

  return (
    <div
      className="fixed inset-0 z-[60] bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md bg-white rounded-xl shadow-2xl border border-stone-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
          <div className="font-medium text-stone-900">Дублировать модель</div>
          <button onClick={onCancel} className="p-1 hover:bg-stone-100 rounded">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div className="text-xs text-stone-500">
            Создать копию <span className="font-mono">{srcKod}</span> с новым kod.
            Копируется только запись modeli_osnova — без вариаций, артикулов и SKU.
          </div>
          <input
            autoFocus
            type="text"
            value={kod}
            onChange={(e) => setKod(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Например, VukiV2"
            className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 font-mono"
          />
          {error && <div className="text-xs text-red-600">{error}</div>}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            onClick={submit}
            disabled={pending}
            className="px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-50"
          >
            {pending ? "Создаём…" : "Дублировать"}
          </button>
        </div>
      </div>
    </div>
  )
}

function ArchiveModal({
  kod, onCancel, onConfirm, pending,
}: {
  kod: string
  onCancel: () => void
  onConfirm: () => void
  pending: boolean
}) {
  return (
    <div
      className="fixed inset-0 z-[60] bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md bg-white rounded-xl shadow-2xl border border-stone-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
          <div className="font-medium text-stone-900">Архивировать модель</div>
          <button onClick={onCancel} className="p-1 hover:bg-stone-100 rounded">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-2">
          <div className="text-sm text-stone-700">
            Архивировать модель <span className="font-mono font-medium">{kod}</span> и все её
            вариации, артикулы и SKU?
          </div>
          <div className="text-xs text-stone-500">
            Откатить через UI нельзя. Каскад: modeli_osnova → Архив, артикулы → Выводим, SKU
            (WB/OZON/Сайт/Lamoda) → Архив.
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className="px-3 py-1.5 text-sm text-white bg-red-600 hover:bg-red-700 rounded-md disabled:opacity-50"
          >
            {pending ? "Архивируем…" : "Архивировать"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Modal-overlay wrapper that listens to ?model=KOD ──────────────────────

/**
 * `ModelCardModal` — top-level entry that listens to `?model=KOD` in URL and
 * renders the {@link ModelCard} as a modal overlay above whatever catalog
 * page is currently mounted (typically Matrix B1).
 */
export function ModelCardModal() {
  const [searchParams, setSearchParams] = useSearchParams()
  const kod = searchParams.get("model")
  const close = useCallback(() => {
    const sp = new URLSearchParams(searchParams)
    sp.delete("model")
    sp.delete("tab")
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams])

  if (!kod) return null
  return <ModelCard kod={kod} onClose={close} />
}

// Convenience: if anyone wants to use the LevelBadge type re-exported.
export type { FieldLevelKind, ReactNode }
