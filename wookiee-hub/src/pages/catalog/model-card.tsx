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
  useRef,
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
  HelpCircle,
  Info,
  Link2,
  Loader2,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react"

import { supabase } from "@/lib/supabase"
import {
  FIELD_LEVEL,
  type FieldLevel as FieldLevelKind,
} from "@/types/catalog"
import {
  archiveModel,
  type AuditEntry,
  bulkAddSizeToArtikuly,
  bulkCreateArtikuly,
  bulkInsertTovary,
  bulkUpdateTovaryStatus,
  duplicateModel,
  fetchAllTags,
  fetchAttributesForCategory,
  fetchAtributy,
  insertAtribut,
  linkAtributToKategoriya,
  type Atribut,
  type AtributPayload,
  fetchAuditFor,
  fetchBrendy,
  fetchFabriki,
  fetchImportery,
  fetchKategorii,
  fetchKollekcii,
  fetchModelDetail,
  fetchRazmery,
  fetchSemeystvaCvetov,
  fetchSertifikaty,
  fetchSizesForModel,
  fetchStatusy,
  fetchTipyKollekciy,
  fetchUpakovki,
  getCatalogAssetSignedUrl,
  insertTovar,
  insertVariation,
  makeStoragePathForModelHeader,
  updateModel,
  type CvetRow,
  type ModelDetail,
  type ModelOsnovaPayload,
  type ModelVariation,
  type Razmer,
  type Sertifikat,
  type TovarChannel,
  type Upakovka,
} from "@/lib/catalog/service"
import {
  AssetUploader,
  AttributeControl,
  CellText,
  CompletenessRing,
  FieldWrap,
  LevelBadge,
  NumberField,
  RefModal,
  SelectField,
  StatusBadge,
  TagsCombobox,
  TextField,
  TextareaField,
  Tooltip,
} from "@/components/catalog/ui"
import { colorSwatchStyle, computeCompleteness, relativeDate } from "@/lib/catalog/color-utils"
import { useAvailableColors } from "@/hooks/use-available-colors"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"
import { compareRazmer } from "@/lib/catalog/size-utils"

// ─── Local helpers ─────────────────────────────────────────────────────────

// W2.3: `TIPY_KOLLEKCII` хардкод убран — теперь справочник `tipy_kollekciy`
// + FK `modeli_osnova.tip_kollekcii_id`. См. fetchTipyKollekciy().

// Default lineup (XS..XXL) — fallback на случай, если БД-запрос ещё грузится
// или модель не имеет ни одной записи в junction `modeli_osnova_razmery`.
// Источник истины — БД через `fetchSizesForModel` (W2.1).
const DEFAULT_SIZES_LINEUP = ["XS", "S", "M", "L", "XL", "XXL"] as const

// ─── Hint helpers (W1.6) ───────────────────────────────────────────────────
// (?) icon next to a field label. На hover показывает подсказку, что
// именно вводить — формат ссылки или единицы измерения.

/** (?) Tooltip icon used inline next to a label. */
function HintIcon({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <HelpCircle
        className="w-3 h-3 text-stone-400 hover:text-stone-600 cursor-help"
        aria-label="Подсказка"
      />
    </Tooltip>
  )
}

/**
 * Wraps a FieldWrap-based field (TextField / NumberField / SelectField) and
 * renders a (?) icon overlay in the top-right of the field block, vertically
 * aligned with the label row (which uses `mb-1` spacing inside FieldWrap).
 * Since fields.tsx is owned by another wave, the icon is positioned
 * absolutely above the field instead of injected into the label's flex row.
 */
function FieldWithHint({ hint, children }: { hint: string; children: ReactNode }) {
  return (
    <div className="relative">
      {children}
      <div className="absolute top-0 right-0 z-10 flex items-center h-[18px]">
        <HintIcon text={hint} />
      </div>
    </div>
  )
}

/**
 * Drop-in replacement for `<FieldWrap label="...">` that renders the label
 * row inline with a (?) hint icon. Used in model-card.tsx only.
 */
function FieldWrapWithHint({
  label,
  hint,
  level,
  full,
  bottomHint,
  children,
}: {
  label: string
  hint: string
  level?: FieldLevelKind
  full?: boolean
  bottomHint?: string
  children: ReactNode
}) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <div className="flex items-center gap-1.5 mb-1">
        <label className="block text-[11px] uppercase tracking-wider text-stone-500">{label}</label>
        <HintIcon text={hint} />
        {level && <LevelBadge level={level} />}
      </div>
      {children}
      {bottomHint && <div className="text-[10px] text-stone-400 mt-1">{bottomHint}</div>}
    </div>
  )
}

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
    brand_id: m.brand_id ?? null,
    kategoriya_id: m.kategoriya_id ?? null,
    kollekciya_id: m.kollekciya_id ?? null,
    fabrika_id: m.fabrika_id ?? null,
    status_id: m.status_id ?? null,
    tip_kollekcii: m.tip_kollekcii ?? null,
    tip_kollekcii_id: m.tip_kollekcii_id ?? null,
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

/**
 * Numeric input that reads/writes a string value (DB column is text but the
 * field is conceptually numeric, e.g. `srok_proizvodstva` — text in БД,
 * "дни" по смыслу). Visual parity with `NumberField` — same suffix slot, same
 * styling. Browser blocks non-numeric input via `type="number"`.
 */
function NumericStringField({
  label, value, onChange, suffix, readonly, level,
  min = 0, step = "any",
}: {
  label: string
  value?: string | null
  onChange?: (v: string) => void
  suffix?: string
  readonly?: boolean
  level?: FieldLevelKind
  min?: number | string
  step?: number | string
}) {
  return (
    <FieldWrap label={label} level={level}>
      {readonly ? (
        <div className="px-2.5 py-1.5 text-sm text-stone-900 tabular-nums">
          {value ? (
            <>{value}{suffix && <span className="text-stone-400 ml-1">{suffix}</span>}</>
          ) : (
            <span className="text-stone-400 italic">не задано</span>
          )}
        </div>
      ) : (
        <div className="relative">
          <input
            type="number"
            inputMode="numeric"
            min={min}
            step={step}
            value={value ?? ""}
            onChange={(e) => onChange?.(e.target.value)}
            className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 tabular-nums pr-10"
          />
          {suffix && (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-stone-400">{suffix}</span>
          )}
        </div>
      )}
    </FieldWrap>
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
  value, onChange, readonly, level, lineup, loading,
}: {
  value: string[]
  onChange: (v: string[]) => void
  readonly: boolean
  level?: FieldLevelKind
  /** Available sizes for this model (driven by `modeli_osnova_razmery` junction). */
  lineup: readonly string[]
  loading?: boolean
}) {
  const toggle = (s: string) => {
    if (readonly) return
    if (value.includes(s)) onChange(value.filter((x) => x !== s))
    else onChange([...value, s])
  }
  return (
    <FieldWrap label="Размерная линейка" level={level} full>
      <div className="flex flex-wrap gap-1.5">
        {loading && lineup.length === 0 ? (
          <span className="text-[11px] text-stone-400 italic">загрузка…</span>
        ) : (
          lineup.map((s) => {
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
          })
        )}
      </div>
      {!readonly && lineup.length > 0 && (
        <div className="text-[10px] text-stone-400 mt-2">
          Клик по чипу — включить/выключить размер.
        </div>
      )}
    </FieldWrap>
  )
}

// ─── Tab type + props passed into each tab ────────────────────────────────

type TabId = "description" | "attributes" | "articles" | "sku" | "content" | "history"

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
  m, draft, setDraft, editing, modelOsnovaId,
}: TabContentProps) {
  const queryClient = useQueryClient()
  const brendyQ = useQuery({
    queryKey: ["catalog", "brendy"],
    queryFn: fetchBrendy,
    staleTime: 5 * 60 * 1000,
  })
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
  const tipyKollekciyQ = useQuery({
    queryKey: ["catalog", "tipy-kollekciy"],
    queryFn: fetchTipyKollekciy,
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
  // W2.1 — размерная линейка модели из БД (junction `modeli_osnova_razmery`),
  // вместо хардкода `SIZES_LINEUP`.
  const modelSizesQ = useQuery<Razmer[]>({
    queryKey: ["catalog", "model-sizes", modelOsnovaId],
    queryFn: () => fetchSizesForModel(modelOsnovaId),
    staleTime: 5 * 60 * 1000,
  })

  const set = (k: keyof ModelDraft, v: unknown) => {
    if (!draft) return
    setDraft({ ...draft, [k]: v as never })
  }

  const brendy = brendyQ.data ?? []
  const kategorii = kategoriiQ.data ?? []
  const kollekcii = kollekciiQ.data ?? []
  const tipyKollekciy = tipyKollekciyQ.data ?? []
  const fabriki = fabrikiQ.data ?? []
  const statusy = (statusyQ.data ?? []).filter((s) => s.tip === "model")
  // Размерная линейка из БД. Если junction-таблица ещё не заполнена для модели,
  // показываем дефолтный XS..XXL, чтобы UI не «исчезал» во время бэкфилла.
  const modelSizeLineup: readonly string[] = (modelSizesQ.data ?? []).length > 0
    ? (modelSizesQ.data ?? []).map((r) => r.nazvanie)
    : DEFAULT_SIZES_LINEUP

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
          {/*
            W3.2 — Бренд (REQUIRED). FK to brendy(id), NOT NULL после
            миграции W3.1. Если в БД ещё не выставлен — UI всё равно даёт
            редактировать, ошибка проявится на save.
          */}
          <SelectField
            label="Бренд *"
            value={view.brand_id ?? ""}
            options={brendy.map((b) => ({ id: b.id, nazvanie: b.nazvanie }))}
            onChange={(v) => {
              const id = typeof v === "number" ? v : v === "" || v == null ? null : Number(v)
              set("brand_id", id)
            }}
            readonly={!editing}
            level={lvl("brand_id")}
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
          <SelectField
            label="Тип коллекции"
            value={view.tip_kollekcii_id ?? ""}
            options={tipyKollekciy.map((t) => ({ id: t.id, nazvanie: t.nazvanie }))}
            onChange={(v) => {
              // W2.3 dual-write: FK + текстовая колонка (для back-compat).
              const id = typeof v === "number" ? v : v === "" || v == null ? null : Number(v)
              const next: ModelDraft = {
                ...(draft as ModelDraft),
                tip_kollekcii_id: id,
                tip_kollekcii: id == null
                  ? null
                  : tipyKollekciy.find((t) => t.id === id)?.nazvanie ?? null,
              }
              setDraft(next)
            }}
            readonly={!editing}
            level={lvl("tip_kollekcii_id")}
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

      {/* W5.2: header image для модели — путь хранится в modeli_osnova.header_image_url,
         сам файл — в Supabase Storage bucket catalog-assets, доступ через signed URL.
         Upload/delete пишут в БД напрямую (минуя draft/save flow), поэтому компонент
         доступен и в read-mode, и в editing — modelToDraft не выгружает header_image_url
         в draft, так что обычный «Сохранить» не перетрёт значение. */}
      <Section label="Фото модели" hint="Хедер карточки и превью в матрице каталога">
        <AssetUploader
          kind="image"
          path={m.header_image_url ?? null}
          buildPath={(file) => makeStoragePathForModelHeader(modelOsnovaId, file.type)}
          onChange={async (newPath) => {
            await updateModel(m.kod, { header_image_url: newPath })
            await queryClient.invalidateQueries({ queryKey: ["catalog", "model", m.kod] })
            await queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
            await queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
          }}
          label="Хедер модели"
        />
      </Section>

      <Section label="Производство">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <SizeLineupField
            value={sizes}
            onChange={(v) => set("razmery_modeli_arr", v)}
            readonly={!editing}
            level={lvl("razmery_modeli")}
            lineup={modelSizeLineup}
            loading={modelSizesQ.isLoading}
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
          <FieldWithHint hint="Срок производства в днях.">
            <NumericStringField
              label="Срок производства"
              value={view.srok_proizvodstva ?? ""}
              onChange={(v) => set("srok_proizvodstva", v)}
              suffix="дни"
              min={0}
              step={1}
              readonly={!editing}
              level={lvl("srok_proizvodstva")}
            />
          </FieldWithHint>
          <FieldWithHint hint="Кратность короба (шт).">
            <NumberField
              label="Кратность короба"
              value={view.kratnost_koroba ?? null}
              onChange={(v) => set("kratnost_koroba", v)}
              suffix="шт"
              min={0}
              step={1}
              readonly={!editing}
              level={lvl("kratnost_koroba")}
            />
          </FieldWithHint>
          <FieldWithHint hint="Вес одного товара (кг).">
            <NumberField
              label="Вес"
              value={view.ves_kg ?? null}
              onChange={(v) => set("ves_kg", v)}
              suffix="кг"
              min={0}
              step={0.01}
              readonly={!editing}
              level={lvl("ves_kg")}
            />
          </FieldWithHint>
          <FieldWithHint hint="Размер короба (см).">
            <NumberField
              label="Длина"
              value={view.dlina_cm ?? null}
              onChange={(v) => set("dlina_cm", v)}
              suffix="см"
              min={0}
              step={0.01}
              readonly={!editing}
              level={lvl("dlina_cm")}
            />
          </FieldWithHint>
          <FieldWithHint hint="Размер короба (см).">
            <NumberField
              label="Ширина"
              value={view.shirina_cm ?? null}
              onChange={(v) => set("shirina_cm", v)}
              suffix="см"
              min={0}
              step={0.01}
              readonly={!editing}
              level={lvl("shirina_cm")}
            />
          </FieldWithHint>
          <FieldWithHint hint="Размер короба (см).">
            <NumberField
              label="Высота"
              value={view.vysota_cm ?? null}
              onChange={(v) => set("vysota_cm", v)}
              suffix="см"
              min={0}
              step={0.01}
              readonly={!editing}
              level={lvl("vysota_cm")}
            />
          </FieldWithHint>
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
  // W6.1: реестр атрибутов в БД (таблица `atributy`). fetchAttributesForCategory
  // возвращает полный `Atribut[]` с label/type/options — без вторичного
  // маппинга через `ALL_ATTRIBUTES`.
  const attrKeysQ = useQuery({
    queryKey: ["catalog", "kategoriya-atributy", m.kategoriya_id],
    queryFn: () => fetchAttributesForCategory(m.kategoriya_id as number),
    enabled: m.kategoriya_id != null,
    staleTime: 5 * 60 * 1000,
  })
  const attrs: Atribut[] = attrKeysQ.data ?? []
  const [addOpen, setAddOpen] = useState(false)

  const set = (k: string, v: unknown) => {
    if (!draft) return
    setDraft({ ...draft, [k]: v as never })
  }
  const view = (editing && draft
    ? (draft as unknown as Record<string, unknown>)
    : (m as unknown as Record<string, unknown>))

  // W9.20 — прогресс заполнения атрибутов: считаем сколько из `attrs` имеют
  // непустое значение в текущем view (draft или сохранённой модели).
  const filledCount = useMemo(() => {
    return attrs.filter((a) => {
      const v = view[a.key]
      if (v == null) return false
      if (typeof v === "string") return v.trim().length > 0
      if (Array.isArray(v)) return v.length > 0
      return true
    }).length
  }, [attrs, view])
  const totalCount = attrs.length
  const pct = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0

  const sectionHeader = (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <span>{totalCount > 0 ? `${totalCount} атрибутов настроены для этой категории` : "Атрибуты не настроены"}</span>
        {totalCount > 0 && (
          <span className="inline-flex items-center gap-1.5 text-[11px] text-stone-500">
            <span>Заполнено {filledCount} из {totalCount}</span>
            <span className="w-24 h-1.5 rounded-full bg-stone-100 overflow-hidden">
              <span
                className="block h-full bg-stone-900 transition-all"
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="tabular-nums">{pct}%</span>
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => setAddOpen(true)}
        disabled={m.kategoriya_id == null}
        title={m.kategoriya_id != null ? "Создать новый атрибут и привязать к этой категории" : "У модели не указана категория"}
        className="px-2.5 py-1 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-800"
      >
        <Plus className="w-3 h-3" /> Новый атрибут
      </button>
    </div>
  )

  return (
    <>
      <Section
        label={`Атрибуты категории «${m.kategoriya ?? "—"}»`}
        hint={sectionHeader as unknown as string}
      >
        {attrs.length === 0 ? (
          <div className="text-sm text-stone-400 italic">
            Нет специфичных атрибутов для этой категории. Нажмите «+ Новый атрибут» чтобы создать первый.
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">
            {attrs.map((a) => {
              const lvl = FIELD_LEVEL[a.key] ?? "model"
              return (
                <AttributeControl
                  key={a.key}
                  atribut={a}
                  value={view[a.key]}
                  onChange={(v) => set(a.key, v)}
                  readonly={!editing}
                  level={lvl}
                />
              )
            })}
          </div>
        )}
      </Section>
      {addOpen && m.kategoriya_id != null && (
        <AddAtributModal
          kategoriyaId={m.kategoriya_id}
          existingAtributIds={new Set(attrs.map((a) => a.id))}
          onClose={() => setAddOpen(false)}
        />
      )}
    </>
  )
}

// W9.14 — модалка для создания нового атрибута + привязки к текущей категории.
// Также позволяет привязать существующий (не связанный с этой категорией) атрибут.
function AddAtributModal({
  kategoriyaId,
  existingAtributIds,
  onClose,
}: {
  kategoriyaId: number
  existingAtributIds: Set<number>
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<"create" | "link">("create")
  const [key, setKey] = useState("")
  const [label, setLabel] = useState("")
  const [type, setType] = useState<"text" | "number" | "select" | "multiselect" | "boolean">("text")
  const [optionsText, setOptionsText] = useState("")
  const [linkAtributId, setLinkAtributId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const allAtributyQ = useQuery({
    queryKey: ["catalog", "atributy", "all"],
    queryFn: fetchAtributy,
    staleTime: 5 * 60 * 1000,
  })
  const linkableAtributy = useMemo(
    () => (allAtributyQ.data ?? []).filter((a) => !existingAtributIds.has(a.id)),
    [allAtributyQ.data, existingAtributIds],
  )

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["catalog", "kategoriya-atributy", kategoriyaId] })
    queryClient.invalidateQueries({ queryKey: ["catalog", "atributy"] })
  }

  const createMut = useMutation({
    mutationFn: async () => {
      if (mode === "link") {
        if (linkAtributId == null) throw new Error("Выберите атрибут из списка")
        await linkAtributToKategoriya(linkAtributId, kategoriyaId)
        return
      }
      const k = key.trim()
      const l = label.trim()
      if (!k) throw new Error("Укажите внутренний key атрибута (латиница, snake_case)")
      if (!l) throw new Error("Укажите подпись атрибута для UI")
      const options = (type === "select" || type === "multiselect")
        ? optionsText.split(",").map((s) => s.trim()).filter(Boolean)
        : []
      const payload: AtributPayload = {
        key: k,
        label: l,
        type: type as never,
        options: options.length > 0 ? options : undefined,
        default_value: null,
        helper_text: null,
      }
      const created = await insertAtribut(payload)
      await linkAtributToKategoriya(created.id, kategoriyaId)
    },
    onSuccess: () => {
      invalidate()
      onClose()
    },
    onError: (e: unknown) => setError(translateError(e)),
  })

  return (
    <div
      className="fixed inset-0 bg-stone-900/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl border border-stone-200 w-full max-w-md p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-medium text-stone-900">Новый атрибут</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700">×</button>
        </div>
        <div className="flex gap-2 mb-4 text-xs">
          <button
            type="button"
            onClick={() => setMode("create")}
            className={`px-2.5 py-1 rounded-md border ${mode === "create" ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-700 border-stone-200"}`}
          >
            Создать новый
          </button>
          <button
            type="button"
            onClick={() => setMode("link")}
            className={`px-2.5 py-1 rounded-md border ${mode === "link" ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-700 border-stone-200"}`}
          >
            Подключить существующий
          </button>
        </div>

        {mode === "create" ? (
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] text-stone-500 mb-1">Внутренний key (snake_case)</label>
              <input
                type="text"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="material_sostav"
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400"
              />
            </div>
            <div>
              <label className="block text-[11px] text-stone-500 mb-1">Подпись для UI</label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Состав материала"
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400"
              />
            </div>
            <div>
              <label className="block text-[11px] text-stone-500 mb-1">Тип значения</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as never)}
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400 bg-white"
              >
                <option value="text">Текст</option>
                <option value="number">Число</option>
                <option value="boolean">Да / Нет</option>
                <option value="select">Один из списка</option>
                <option value="multiselect">Несколько из списка</option>
              </select>
            </div>
            {(type === "select" || type === "multiselect") && (
              <div>
                <label className="block text-[11px] text-stone-500 mb-1">Варианты значений (через запятую)</label>
                <input
                  type="text"
                  value={optionsText}
                  onChange={(e) => setOptionsText(e.target.value)}
                  placeholder="хлопок, лён, шёлк"
                  className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400"
                />
              </div>
            )}
          </div>
        ) : (
          <div>
            <label className="block text-[11px] text-stone-500 mb-1">Атрибут из общего справочника</label>
            <select
              value={linkAtributId ?? ""}
              onChange={(e) => setLinkAtributId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md outline-none focus:border-stone-400 bg-white"
            >
              <option value="">— выберите атрибут —</option>
              {linkableAtributy.map((a) => (
                <option key={a.id} value={a.id}>{a.label} ({a.type})</option>
              ))}
            </select>
            <p className="text-[11px] text-stone-500 mt-2">
              Показаны атрибуты, ещё не привязанные к этой категории.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2.5 py-1.5">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-stone-700 bg-white border border-stone-200 hover:bg-stone-50 rounded-md"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => { setError(null); createMut.mutate() }}
            disabled={createMut.isPending}
            className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-50"
          >
            {createMut.isPending ? "Сохраняем…" : (mode === "create" ? "Создать и привязать" : "Подключить")}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Tab 3: Articles ───────────────────────────────────────────────────────

function TabArticles({ m, hexByCvet, openColor }: TabContentProps) {
  // W10.29 — стабильный порядок: variantKod → cvet.color_code. Смена статуса
  // не должна менять порядок строк.
  const allArts = useMemo(() => {
    const rows = m.modeli.flatMap((v) =>
      v.artikuly.map((a) => ({ ...a, variantKod: v.kod, importerName: v.importer_nazvanie })),
    )
    return rows.sort((a, b) => {
      const variantCmp = (a.variantKod ?? "").localeCompare(b.variantKod ?? "", "ru", { numeric: true })
      if (variantCmp !== 0) return variantCmp
      return (a.cvet_color_code ?? "").localeCompare(b.cvet_color_code ?? "", "ru", { numeric: true })
    })
  }, [m.modeli])
  const [addOpen, setAddOpen] = useState(false)
  const hasVariations = m.modeli.length > 0
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
          onClick={() => setAddOpen(true)}
          disabled={!hasVariations}
          title={hasVariations ? "Добавить цвет — создать артикулы из доступных цветов категории" : "Сначала создайте вариацию модели"}
          className="px-2.5 py-1 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-800"
        >
          <Plus className="w-3 h-3" /> Добавить цвет
        </button>
      </div>
      {addOpen && (
        <AddArtikulModal
          modelKod={m.kod}
          modelRazmery={parseRazmery(m.razmery_modeli)}
          kategoriyaId={m.kategoriya_id ?? null}
          variations={m.modeli}
          onClose={() => setAddOpen(false)}
        />
      )}
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
            return (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-700"><CellText title={a.artikul}>{a.artikul}</CellText></td>
                <td className="px-3 py-2 font-mono text-xs text-stone-600"><CellText title={a.variantKod ?? ""}>{a.variantKod}</CellText></td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => a.cvet_color_code && openColor(a.cvet_color_code)}
                    disabled={!a.cvet_color_code}
                    className="flex items-center gap-1.5 min-w-0 max-w-full hover:bg-stone-100 rounded px-1 py-0.5 -mx-1 disabled:cursor-default"
                  >
                    <span
                      className="inline-block w-3.5 h-3.5 rounded ring-1 ring-stone-200 shrink-0"
                      style={{ ...colorSwatchStyle(hex) }}
                    />
                    <CellText className="font-mono text-xs text-stone-700" title={a.cvet_color_code ?? ""}>
                      {a.cvet_color_code ?? "—"}
                    </CellText>
                    {a.cvet_nazvanie && (
                      <CellText className="text-stone-500 text-xs" title={a.cvet_nazvanie}>{a.cvet_nazvanie}</CellText>
                    )}
                  </button>
                </td>
                <td className="px-3 py-2"><StatusBadge statusId={a.status_id} compact /></td>
                <td className="px-3 py-2 font-mono text-[11px] text-stone-500 tabular-nums">
                  <CellText title={a.nomenklatura_wb != null ? String(a.nomenklatura_wb) : ""}>{a.nomenklatura_wb ?? "—"}</CellText>
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                  <CellText title={a.artikul_ozon ?? ""}>{a.artikul_ozon ?? "—"}</CellText>
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

// ─── Add-artikul modal (W4.3) ──────────────────────────────────────────────
//
// Палитра цветов + чекбоксы. По умолчанию выбраны все цвета модели, которые
// ещё НЕ привязаны к выбранной вариации (исключение дублей). Кнопка «Создать»
// делает bulk-create через `bulkCreateArtikuly`.
//
// W10.9 — секция «Размеры» multi-select. Источник — `razmery_modeli` модели
// (CSV), маппинг nazvanie → razmer_id берётся из глобального справочника
// `razmery` через `fetchRazmery`. По умолчанию выбраны все размеры модели.
//
// artikul генерируется автоматически как `${modeli.kod}/${cveta.color_code}`
// — это поведение сервиса, не UI. См. `insertArtikul` в service.ts.
function AddArtikulModal({
  modelKod,
  modelRazmery,
  kategoriyaId,
  variations,
  onClose,
}: {
  modelKod: string
  /** Размеры модели (parseRazmery(m.razmery_modeli)). Может быть пустым. */
  modelRazmery: string[]
  /** W9.12 — filter colour palette by model category. */
  kategoriyaId: number | null
  variations: ModelVariation[]
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  // Default — first variation. Если их больше одной, юзер может переключиться.
  const [variationId, setVariationId] = useState<number>(variations[0]?.id ?? 0)
  const [selectedCvety, setSelectedCvety] = useState<Set<number>>(new Set())
  // W10.9 — выбранные размеры модели. Default — ВСЕ размеры модели.
  const [selectedRazmery, setSelectedRazmery] = useState<Set<string>>(
    () => new Set(modelRazmery),
  )
  // W9.11 — per-cvet custom artikul name. Empty/undefined ⇒ use generated.
  // Map keyed by cvet_id so values persist across select/deselect toggles
  // until variation switch (then we reset along with selection).
  const [customNames, setCustomNames] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)

  // W9.12 — palette filtered by category. Legacy colours (no category tags)
  // remain visible everywhere.
  const { colors: categoryColors, isLoading: colorsLoading } =
    useAvailableColors(kategoriyaId)

  // W10.9 — справочник `razmery` для маппинга nazvanie → id при создании SKU.
  const razmeryQ = useQuery({
    queryKey: ["catalog", "razmery"],
    queryFn: fetchRazmery,
    staleTime: 5 * 60 * 1000,
  })
  const razmeryIdByName = useMemo(() => {
    const m = new Map<string, number>()
    for (const r of razmeryQ.data ?? []) {
      if (r.nazvanie) m.set(r.nazvanie, r.id)
    }
    return m
  }, [razmeryQ.data])

  // Already-attached cveta ids — для исключения из выбора (нельзя создать
  // дубликат `${kod}/${color_code}` — артикул должен быть уникальным).
  const attachedCvetIds = useMemo(() => {
    const v = variations.find((x) => x.id === variationId)
    if (!v) return new Set<number>()
    return new Set(v.artikuly.map((a) => a.cvet_id).filter((id): id is number => id != null))
  }, [variationId, variations])

  // Available colours — category-filtered, minus already attached.
  const availableCveta: CvetRow[] = useMemo(() => {
    return categoryColors.filter((c) => !attachedCvetIds.has(c.id))
  }, [categoryColors, attachedCvetIds])

  // W9.11 — existing artikul names across ALL variations of this model
  // (lower-cased) for client-side uniqueness pre-check. Server-side guarantee
  // is the global UNIQUE constraint `artikuly_artikul_key`; this is UX only —
  // catch duplicates BEFORE submit instead of surfacing a translated 23505.
  const existingArtikulNames = useMemo(() => {
    const s = new Set<string>()
    for (const v of variations) {
      for (const a of v.artikuly) {
        if (a.artikul) s.add(a.artikul.toLowerCase())
      }
    }
    return s
  }, [variations])

  // Reset selection + custom names when variation changes (different attached set).
  useEffect(() => {
    setSelectedCvety(new Set())
    setCustomNames({})
    setError(null)
  }, [variationId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  // W10.9 + W10.37 — bulk-create артикулов И SKU за один submit.
  //
  // Шаги:
  //   1. `bulkCreateArtikuly(variationId, entries)` — создаёт N артикулов.
  //   2. Для каждого нового артикула × каждый выбранный размер собирается
  //      cross-product → `bulkInsertTovary(payload)` за один батч. SKU
  //      создаются с дефолтным статусом «План» во всех 3-х каналах.
  // Если шаг 1 успешен, а шаг 2 падает — артикулы останутся (без SKU),
  // пользователь увидит ошибку и сможет добавить SKU вручную через TabSKU.
  // Это компромисс: rollback артикулов потребовал бы транзакции на сервере,
  // которой у Supabase REST нет.
  // Дубликаты `(artikul_id, razmer_id)` тихо пропускаются `bulkInsertTovary`
  // (UNIQUE constraint на уровне DB + явный probe в самом сервисе).
  const createMut = useMutation({
    mutationFn: async (
      entries: { cvetId: number; customArtikul?: string }[],
    ) => {
      const created = await bulkCreateArtikuly(variationId, entries)
      // Resolve razmer ids from selected names. Размеры, которых нет в
      // справочнике, тихо пропускаются — это data-quality (razmery_modeli
      // содержит размер, отсутствующий в таблице `razmery`). Лучше дать
      // создать N×M-1, чем падать.
      const razmerIds: number[] = []
      for (const name of selectedRazmery) {
        const id = razmeryIdByName.get(name)
        if (id != null) razmerIds.push(id)
      }
      if (created.length > 0 && razmerIds.length > 0) {
        const payload: { artikulId: number; razmerId: number }[] = []
        for (const a of created) {
          for (const rid of razmerIds) {
            payload.push({ artikulId: a.id, razmerId: rid })
          }
        }
        await bulkInsertTovary(payload)
      }
      return created
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog", "model", modelKod] })
      queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["catalog", "cveta-with-usage"] })
      onClose()
    },
    onError: (e: unknown) => {
      setError(translateError(e))
    },
  })

  const toggle = (id: number) => {
    setSelectedCvety((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => setSelectedCvety(new Set(availableCveta.map((c) => c.id)))
  const clearAll = () => setSelectedCvety(new Set())

  const selectedVariation = variations.find((v) => v.id === variationId)
  const selectedCount = selectedCvety.size

  // W9.11 — generated default for a given cvet (used as input placeholder/value).
  const buildDefaultName = useCallback(
    (cvet: CvetRow): string => {
      const kod = selectedVariation?.kod ?? modelKod
      return `${kod}/${cvet.color_code}`
    },
    [selectedVariation, modelKod],
  )

  // Resolve effective name for a selected cvet: user-typed value (if any)
  // takes precedence over the generated default.
  const effectiveName = useCallback(
    (cvet: CvetRow): string => {
      const custom = customNames[cvet.id]
      if (custom !== undefined && custom.trim().length > 0) return custom.trim()
      return buildDefaultName(cvet)
    },
    [customNames, buildDefaultName],
  )

  // W9.11 — per-row validation. Returns null if valid, else human message.
  const validateRow = useCallback(
    (cvet: CvetRow, allSelected: CvetRow[]): string | null => {
      const raw = customNames[cvet.id]
      // If user did not touch the input, default value applies — assume valid
      // (default = `${kod}/${color_code}`, which is non-empty and not present
      // in attached colours of this variation by construction).
      const name = effectiveName(cvet)
      if (!name) return "Имя не может быть пустым"
      if (raw !== undefined && raw.trim().length === 0) {
        return "Имя не может быть пустым"
      }
      // Spaces are not allowed in the historical `${kod}/${color_code}` format
      // and would clash with how artikul is referenced downstream (Sheets,
      // marketplaces). Keep the constraint conservative.
      if (/\s/.test(name)) return "Без пробелов"
      // Uniqueness vs already-existing artikuly across the model.
      if (existingArtikulNames.has(name.toLowerCase())) {
        return "Такой артикул уже существует"
      }
      // Uniqueness within the current batch (two selected rows could collide
      // if the user edits one to match another).
      const lower = name.toLowerCase()
      const collisions = allSelected.filter(
        (c) => effectiveName(c).toLowerCase() === lower,
      )
      if (collisions.length > 1) return "Дубликат в этой форме"
      return null
    },
    [customNames, effectiveName, existingArtikulNames],
  )

  const selectedCveta = useMemo(
    () => availableCveta.filter((c) => selectedCvety.has(c.id)),
    [availableCveta, selectedCvety],
  )

  // W10.9 — сколько выбранных размеров реально создадутся (есть в справочнике).
  // Размер из `razmery_modeli`, отсутствующий в таблице `razmery` — data-quality
  // issue: SKU для него создать нельзя. Считаем только resolvable.
  const resolvedRazmerCount = useMemo(() => {
    let n = 0
    for (const r of selectedRazmery) {
      if (razmeryIdByName.get(r) != null) n += 1
    }
    return n
  }, [selectedRazmery, razmeryIdByName])

  const rowErrors = useMemo(() => {
    const errs: Record<number, string | null> = {}
    for (const c of selectedCveta) {
      errs[c.id] = validateRow(c, selectedCveta)
    }
    return errs
  }, [selectedCveta, validateRow])

  const hasValidationErrors = useMemo(
    () => Object.values(rowErrors).some((e) => e !== null),
    [rowErrors],
  )

  const canSubmit =
    selectedCount > 0 &&
    variationId > 0 &&
    !createMut.isPending &&
    !hasValidationErrors

  const handleSubmit = () => {
    if (!canSubmit) return
    const entries = selectedCveta.map((c) => {
      const raw = customNames[c.id]
      // Send `customArtikul` only when the user actually typed something
      // different from default. Server falls back to generated when missing
      // — keeps the wire payload small and the audit log clean.
      const trimmed = raw?.trim() ?? ""
      if (trimmed.length > 0 && trimmed !== buildDefaultName(c)) {
        return { cvetId: c.id, customArtikul: trimmed }
      }
      return { cvetId: c.id }
    })
    createMut.mutate(entries)
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200 flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200 shrink-0">
          <h2
            className="cat-font-serif text-xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            Создать артикулы
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-stone-100 rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4 overflow-y-auto">
          {/* Variation picker (only if >1) */}
          {variations.length > 1 && (
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">
                Вариация
              </label>
              <select
                value={variationId}
                onChange={(e) => setVariationId(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              >
                {variations.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.kod}{v.importer_nazvanie ? ` · ${v.importer_nazvanie}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          {variations.length === 1 && selectedVariation && (
            <div className="text-xs text-stone-500">
              Вариация: <span className="font-mono text-stone-700">{selectedVariation.kod}</span>
              {selectedVariation.importer_nazvanie ? ` · ${selectedVariation.importer_nazvanie}` : ""}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-[11px] uppercase tracking-wider text-stone-500">
                Палитра цветов
              </label>
              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={selectAll}
                  disabled={availableCveta.length === 0}
                  className="text-stone-600 hover:text-stone-900 underline underline-offset-2 disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
                >
                  Выбрать все
                </button>
                <span className="text-stone-300">·</span>
                <button
                  type="button"
                  onClick={clearAll}
                  disabled={selectedCount === 0}
                  className="text-stone-600 hover:text-stone-900 underline underline-offset-2 disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
                >
                  Очистить
                </button>
              </div>
            </div>

            {colorsLoading ? (
              <div className="text-sm text-stone-400 italic py-6 text-center">Загрузка цветов…</div>
            ) : availableCveta.length === 0 ? (
              <div className="text-sm text-stone-400 italic py-6 text-center">
                {categoryColors.length === 0
                  ? "Для этой категории нет цветов в палитре. Привяжите цвета к категории в справочнике."
                  : "Все доступные цвета уже привязаны к этой вариации"}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-1.5 max-h-[28vh] overflow-y-auto pr-1">
                {availableCveta.map((c) => {
                  const checked = selectedCvety.has(c.id)
                  const previewArtikul = effectiveName(c)
                  return (
                    <label
                      key={c.id}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-md border cursor-pointer text-sm transition-colors ${
                        checked
                          ? "border-stone-900 bg-stone-50"
                          : "border-stone-200 hover:border-stone-400"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(c.id)}
                        className="shrink-0 accent-stone-900"
                      />
                      <span
                        className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
                        style={colorSwatchStyle(c.hex)}
                      />
                      <span className="font-mono text-xs text-stone-700 shrink-0">{c.color_code}</span>
                      {c.cvet && (
                        <span className="text-stone-500 text-xs truncate">{c.cvet}</span>
                      )}
                      <span className="ml-auto font-mono text-[10px] text-stone-400 truncate shrink-0 pl-1">
                        {previewArtikul}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* W9.11 — editable artikul names for selected colours. */}
          {selectedCveta.length > 0 && (
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-2">
                Имена артикулов
              </label>
              <div className="space-y-1.5 max-h-[32vh] overflow-y-auto pr-1">
                {selectedCveta.map((c) => {
                  const defaultName = buildDefaultName(c)
                  const raw = customNames[c.id]
                  const value = raw !== undefined ? raw : defaultName
                  const isCustom = raw !== undefined && raw.trim() !== defaultName
                  const err = rowErrors[c.id]
                  return (
                    <div key={c.id} className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
                          style={colorSwatchStyle(c.hex)}
                          aria-hidden="true"
                        />
                        <span className="font-mono text-xs text-stone-500 shrink-0 w-20 truncate">
                          {c.color_code}
                        </span>
                        <input
                          type="text"
                          value={value}
                          onChange={(e) =>
                            setCustomNames((prev) => ({ ...prev, [c.id]: e.target.value }))
                          }
                          spellCheck={false}
                          autoComplete="off"
                          className={`flex-1 min-w-0 px-2 py-1 text-sm font-mono border rounded-md bg-white outline-none focus:ring-1 ${
                            err
                              ? "border-red-400 focus:border-red-600 focus:ring-red-200"
                              : "border-stone-200 focus:border-stone-900 focus:ring-stone-900"
                          }`}
                          aria-label={`Имя артикула для цвета ${c.color_code}`}
                          aria-invalid={err ? true : undefined}
                        />
                        {isCustom && (
                          <button
                            type="button"
                            onClick={() =>
                              setCustomNames((prev) => {
                                const next = { ...prev }
                                delete next[c.id]
                                return next
                              })
                            }
                            className="shrink-0 text-[11px] text-stone-500 hover:text-stone-900 underline underline-offset-2"
                            title="Вернуть автогенерированное имя"
                          >
                            Сбросить
                          </button>
                        )}
                      </div>
                      {err && (
                        <div className="pl-[5.25rem] text-[11px] text-red-600">{err}</div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* W10.9 — секция «Размеры». Multi-select из razmery_modeli модели. */}
          {modelRazmery.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-[11px] uppercase tracking-wider text-stone-500">
                  Размеры
                </label>
                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => setSelectedRazmery(new Set(modelRazmery))}
                    disabled={selectedRazmery.size === modelRazmery.length}
                    className="text-stone-600 hover:text-stone-900 underline underline-offset-2 disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
                  >
                    Все
                  </button>
                  <span className="text-stone-300">·</span>
                  <button
                    type="button"
                    onClick={() => setSelectedRazmery(new Set())}
                    disabled={selectedRazmery.size === 0}
                    className="text-stone-600 hover:text-stone-900 underline underline-offset-2 disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
                  >
                    Очистить
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {modelRazmery.map((r) => {
                  const checked = selectedRazmery.has(r)
                  const knownId = razmeryIdByName.get(r) != null
                  return (
                    <label
                      key={r}
                      className={`flex items-center gap-1.5 px-2 py-1 text-xs rounded-md border cursor-pointer transition-colors ${
                        checked
                          ? "border-stone-900 bg-stone-50"
                          : "border-stone-200 hover:border-stone-400"
                      } ${!knownId ? "opacity-60" : ""}`}
                      title={
                        !knownId
                          ? "Размер не найден в справочнике razmery — SKU не будет создан"
                          : undefined
                      }
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setSelectedRazmery((prev) => {
                            const next = new Set(prev)
                            if (next.has(r)) next.delete(r)
                            else next.add(r)
                            return next
                          })
                        }
                        className="shrink-0 accent-stone-900"
                      />
                      <span className="font-mono">{r}</span>
                    </label>
                  )
                })}
              </div>
            </div>
          )}

          {error && (
            <div className="px-3 py-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
              {error}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-stone-200 flex items-center justify-between shrink-0 bg-stone-50/50">
          <div className="text-xs text-stone-500">
            {selectedCount === 0 ? (
              <>Выбрано: <span className="font-medium text-stone-700">0</span></>
            ) : (
              <>
                Будет создано:{" "}
                <span className="font-medium text-stone-700">{selectedCount}</span>{" "}
                {selectedCount === 1 ? "артикул" : "артикула"}
                {resolvedRazmerCount > 0 && (
                  <>
                    {" × "}
                    <span className="font-medium text-stone-700">{resolvedRazmerCount}</span>{" "}
                    {resolvedRazmerCount === 1 ? "размер" : "размеров"}
                    {" = "}
                    <span className="font-medium text-stone-700">
                      {selectedCount * resolvedRazmerCount}
                    </span>{" "}
                    SKU
                  </>
                )}
                <span className="ml-2 text-stone-400">· статус «Запуск»</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMut.isPending
                ? "Создаём…"
                : selectedCount > 1
                  ? `Создать ${selectedCount}`
                  : "Создать"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Tab 4: SKU ────────────────────────────────────────────────────────────

// W4.5 — inline-edit статусов SKU.
// Дизайн-выборы (см. PLAN.md row W4.5):
//   * popover — не зависим от @base-ui/@radix: ручная absolute-разметка с
//     click-outside listener (как в `pages/catalog/tovary.tsx::InlineStatusCell`
//     и `matrix.tsx::BulkBar`). Лёгкая, без новых импортов.
//   * options — все `statusy` где `tip='product'` (одинаковый набор для всех
//     четырёх каналов wb/ozon/sayt/lamoda). Это согласовано в PLAN W4.5
//     ("dropdown статусов (только tip='product')"). Канал-специфичные
//     tip-ы ('sayt'/'lamoda') здесь намеренно не используются — спецификация
//     просит единый набор product-статусов для inline-edit.
//   * clear (NULL) — отдельный пункт «—» в начале списка; сетит поле в NULL
//     через `bulkUpdateTovaryStatus(..., null, channel)`.
//   * Стратегия обновления: pessimistic — ждём ответ Supabase, затем
//     invalidate `["catalog", "model", kod]`. Без оптимистики:
//       (a) `kod` не доступен внутри TabSKU без прокидывания пропса;
//       (b) network к Supabase локальный, latency низкий — UX страдает мало.
//     Если задержка станет заметной — добавим `onMutate` с
//     `queryClient.setQueryData` поверх `ModelDetail`.

interface StatusOption {
  id: number
  nazvanie: string
  color: string | null
}

interface InlineStatusCellProps {
  currentStatusId: number | null
  channel: TovarChannel
  options: StatusOption[]
  onChange: (statusId: number | null) => Promise<void>
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

  const onSelect = useCallback(async (id: number | null) => {
    if (saving) return
    setSaving(true)
    try {
      await onChange(id)
      setOpen(false)
    } catch (err) {
      toast.error(translateError(err))
    } finally {
      setSaving(false)
    }
  }, [onChange, saving])

  const current = currentStatusId != null
    ? options.find((s) => s.id === currentStatusId) ?? null
    : null

  return (
    <div className="relative inline-block" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="hover:ring-1 hover:ring-stone-400 rounded-md transition-all"
        title={`Статус ${channel.toUpperCase()} — кликните чтобы изменить`}
      >
        {current
          ? <StatusBadge status={{ nazvanie: current.nazvanie, color: current.color ?? "gray" }} compact />
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
            <button
              type="button"
              disabled={saving}
              onClick={() => onSelect(null)}
              className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-stone-50 rounded text-left text-[11px] text-stone-500 italic disabled:opacity-50"
            >
              — (без статуса)
              {currentStatusId == null && (
                <span className="ml-auto text-[10px] text-emerald-600 not-italic">текущий</span>
              )}
            </button>
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

function TabSKU({ m, hexByCvet }: TabContentProps) {
  const queryClient = useQueryClient()
  const [addSkuOpen, setAddSkuOpen] = useState(false)
  const [bulkAddOpen, setBulkAddOpen] = useState(false)

  // Список всех артикулов модели (для select-полей в модалках)
  const allArtikuly = useMemo(
    () =>
      m.modeli.flatMap((v) =>
        v.artikuly.map((a) => ({
          id: a.id,
          artikul: a.artikul,
          cvet_color_code: a.cvet_color_code,
          variantKod: v.kod,
        })),
      ),
    [m],
  )

  // Все размеры (общий справочник)
  const razmeryQ = useQuery({
    queryKey: ["catalog", "razmery"],
    queryFn: fetchRazmery,
    staleTime: 5 * 60 * 1000,
  })
  const razmery: Razmer[] = razmeryQ.data ?? []

  // W10.29 — стабильная сортировка SKU: variantKod → cvet.color_code → razmer
  // (physical ladder). Не зависит от статусов: смена статуса не должна менять
  // порядок строк (избегаем «прыжков» при клике по статус-pill).
  const allSku = useMemo(() => {
    const rows = m.modeli.flatMap((v) =>
      v.artikuly.flatMap((a) =>
        a.tovary.map((t) => ({
          ...t,
          variantKod: v.kod,
          cvet_color_code: a.cvet_color_code,
          cvet_id: a.cvet_id,
        })),
      ),
    )
    return rows.sort((a, b) => {
      const variantCmp = (a.variantKod ?? "").localeCompare(b.variantKod ?? "", "ru", { numeric: true })
      if (variantCmp !== 0) return variantCmp
      const cvetCmp = (a.cvet_color_code ?? "").localeCompare(b.cvet_color_code ?? "", "ru", { numeric: true })
      if (cvetCmp !== 0) return cvetCmp
      return compareRazmer(a.razmer_nazvanie ?? null, b.razmer_nazvanie ?? null)
    })
  }, [m.modeli])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["catalog", "model", m.kod] })
    queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
    queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
  }

  const insertMut = useMutation({
    mutationFn: ({ artikulId, razmerId }: { artikulId: number; razmerId: number }) =>
      insertTovar(artikulId, razmerId),
    onSuccess: () => {
      setAddSkuOpen(false)
      invalidate()
    },
  })

  const bulkAddMut = useMutation({
    mutationFn: ({ artikulIds, razmerId }: { artikulIds: number[]; razmerId: number }) =>
      bulkAddSizeToArtikuly(artikulIds, razmerId),
    onSuccess: () => {
      setBulkAddOpen(false)
      invalidate()
    },
  })

  const canAdd = allArtikuly.length > 0 && razmery.length > 0

  // Опции артикулов/размеров для select-полей
  const artikulOptions = allArtikuly.map((a) => ({
    value: a.id,
    label: `${a.artikul}${a.cvet_color_code ? " · " + a.cvet_color_code : ""}`,
  }))
  const razmerOptions = razmery.map((r) => ({
    value: r.id,
    label: r.nazvanie ?? `#${r.id}`,
  }))

  const statusyQ = useQuery({
    queryKey: ["catalog", "statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })

  // W4.5 — единый набор product-статусов для всех 4 каналов (см. шапку файла).
  const productStatusOptions: StatusOption[] = useMemo(
    () => (statusyQ.data ?? [])
      .filter((s) => s.tip === "product")
      .map((s) => ({ id: s.id, nazvanie: s.nazvanie, color: s.color })),
    [statusyQ.data],
  )

  const updateStatusMut = useMutation({
    mutationFn: async ({ barkod, statusId, channel }: {
      barkod: string; statusId: number | null; channel: TovarChannel
    }) => {
      await bulkUpdateTovaryStatus([barkod], statusId, channel)
    },
    onSuccess: () => {
      // Перечитываем модель — карточка пересоберёт TabSKU с новыми статусами.
      void queryClient.invalidateQueries({
        queryKey: ["catalog", "model"],
        exact: false,
      })
    },
  })

  const onChangeStatus = useCallback(
    (barkod: string, channel: TovarChannel) =>
      async (statusId: number | null) => {
        await updateStatusMut.mutateAsync({ barkod, statusId, channel })
      },
    [updateStatusMut],
  )

  return (
    <>
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between gap-3">
        <div>
          <div className="font-medium text-stone-900">SKU модели</div>
          <div className="text-xs text-stone-500">
            {allSku.length} SKU · клик по статусу — изменить
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className="px-2.5 py-1 text-xs text-stone-700 bg-white border border-stone-200 rounded-md flex items-center gap-1.5 hover:bg-stone-50 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!canAdd}
            onClick={() => setBulkAddOpen(true)}
            title={
              canAdd
                ? "Добавить один размер сразу всем артикулам модели"
                : "Сначала создайте артикулы и убедитесь, что справочник размеров загружен"
            }
          >
            <Plus className="w-3 h-3" /> Размер ко всем артикулам
          </button>
          <button
            type="button"
            className="px-2.5 py-1 text-xs text-white bg-stone-900 rounded-md flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!canAdd}
            onClick={() => setAddSkuOpen(true)}
            title={
              canAdd
                ? "Создать новый SKU (артикул + размер)"
                : "Сначала создайте артикулы и убедитесь, что справочник размеров загружен"
            }
          >
            <Plus className="w-3 h-3" /> SKU
          </button>
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
              return (
                <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                  <td className="px-3 py-2 font-mono text-xs text-stone-700"><CellText title={t.barkod}>{t.barkod}</CellText></td>
                  <td className="px-3 py-2 font-mono text-xs text-stone-600"><CellText title={t.variantKod ?? ""}>{t.variantKod}</CellText></td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className="inline-block w-3.5 h-3.5 rounded ring-1 ring-stone-200 shrink-0"
                        style={colorSwatchStyle(hex)}
                      />
                      <CellText className="font-mono text-xs" title={t.cvet_color_code ?? ""}>{t.cvet_color_code ?? "—"}</CellText>
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs"><CellText title={t.razmer_nazvanie ?? ""}>{t.razmer_nazvanie ?? "—"}</CellText></td>
                  <td className="px-3 py-2 border-l border-stone-100">
                    <InlineStatusCell
                      currentStatusId={t.status_id ?? null}
                      channel="wb"
                      options={productStatusOptions}
                      onChange={onChangeStatus(t.barkod, "wb")}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <InlineStatusCell
                      currentStatusId={t.status_ozon_id ?? null}
                      channel="ozon"
                      options={productStatusOptions}
                      onChange={onChangeStatus(t.barkod, "ozon")}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <InlineStatusCell
                      currentStatusId={t.status_sayt_id ?? null}
                      channel="sayt"
                      options={productStatusOptions}
                      onChange={onChangeStatus(t.barkod, "sayt")}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <InlineStatusCell
                      currentStatusId={t.status_lamoda_id ?? null}
                      channel="lamoda"
                      options={productStatusOptions}
                      onChange={onChangeStatus(t.barkod, "lamoda")}
                    />
                  </td>
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

    {/* Модалка «+ SKU» — один артикул + один размер */}
    {addSkuOpen && (
      <RefModal
        title="Создать SKU"
        fields={[
          {
            key: "artikul_id",
            label: "Артикул",
            type: "select",
            required: true,
            options: artikulOptions,
            full: true,
            hint: "Артикул, к которому добавляем новый размер",
          },
          {
            key: "razmer_id",
            label: "Размер",
            type: "select",
            required: true,
            options: razmerOptions,
            full: true,
          },
        ]}
        onSave={async (vals) => {
          const artikulId = Number(vals.artikul_id)
          const razmerId = Number(vals.razmer_id)
          if (!Number.isFinite(artikulId) || !Number.isFinite(razmerId)) return
          await insertMut.mutateAsync({ artikulId, razmerId })
        }}
        onCancel={() => setAddSkuOpen(false)}
        saveLabel="Создать"
      />
    )}

    {/* Модалка «+ Размер ко всем артикулам» — multiselect артикулов + один размер */}
    {bulkAddOpen && (
      <RefModal
        title="Размер ко всем артикулам"
        initial={{ artikul_ids: allArtikuly.map((a) => a.id) }}
        fields={[
          {
            key: "artikul_ids",
            label: "Артикулы",
            type: "multiselect",
            required: true,
            options: artikulOptions,
            full: true,
            hint: "По умолчанию выбраны все артикулы модели — снимите ненужные. Артикулы, у которых выбранный размер уже есть, будут пропущены автоматически.",
          },
          {
            key: "razmer_id",
            label: "Размер",
            type: "select",
            required: true,
            options: razmerOptions,
            full: true,
          },
        ]}
        onSave={async (vals) => {
          const raw = vals.artikul_ids
          const ids = Array.isArray(raw)
            ? (raw as Array<string | number>).map((x) => Number(x)).filter((n) => Number.isFinite(n))
            : []
          const razmerId = Number(vals.razmer_id)
          if (ids.length === 0 || !Number.isFinite(razmerId)) return
          await bulkAddMut.mutateAsync({ artikulIds: ids, razmerId })
        }}
        onCancel={() => setBulkAddOpen(false)}
        saveLabel="Создать"
      />
    )}
    </>
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
          <FieldWrapWithHint
            label="Notion · карточка модели"
            hint="Ссылка на страницу в Notion. Скопируй из адресной строки."
            level="model"
            full
          >
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
          </FieldWrapWithHint>

          {/* notion_strategy_link */}
          <FieldWrapWithHint
            label="Notion · продуктовая стратегия"
            hint="Ссылка на стратегию модели."
            level="model"
            full
            bottomHint="Стратегия позиционирования, конкуренты, гипотезы"
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
          </FieldWrapWithHint>

          {/* yandex_disk_link */}
          <FieldWrapWithHint
            label="Яндекс.Диск · фотоконтент"
            hint="Ссылка на папку модели на Яндекс.Диске."
            level="model"
            full
            bottomHint="Папка с фотографиями товара для сайта и МП"
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
          </FieldWrapWithHint>
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

// ─── Tab 6: История (W7.1) ─────────────────────────────────────────────────
//
// Audit log: показывает все изменения по `modeli_osnova` (текущая модель)
// + по каждой вариации (`modeli`). Бэк — таблица `public.audit_log` (см.
// migration 023), триггеры пишут before/after/changed JSONB.

interface AuditRowExt extends AuditEntry {
  /** human-readable label вида "Модель", "Вариация (Wendy)" — рендерится в строке */
  source_label: string
}

function actionBadgeClass(action: AuditEntry["action"]): string {
  switch (action) {
    case "INSERT":
      return "bg-emerald-100 text-emerald-700 border-emerald-200"
    case "UPDATE":
      return "bg-blue-100 text-blue-700 border-blue-200"
    case "DELETE":
      return "bg-red-100 text-red-700 border-red-200"
  }
}

function actionLabel(action: AuditEntry["action"]): string {
  switch (action) {
    case "INSERT":
      return "создано"
    case "UPDATE":
      return "изменено"
    case "DELETE":
      return "удалено"
  }
}

function tableLabel(t: string): string {
  switch (t) {
    case "modeli_osnova":
      return "Модель"
    case "modeli":
      return "Вариация"
    case "artikuly":
      return "Артикул"
    case "tovary":
      return "SKU"
    case "cveta":
      return "Цвет"
    case "brendy":
      return "Бренд"
    case "kollekcii":
      return "Коллекция"
    case "kategorii":
      return "Категория"
    case "sertifikaty":
      return "Сертификат"
    default:
      return t
  }
}

function formatAuditValue(v: unknown): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "string") {
    const s = v.length > 80 ? v.slice(0, 80) + "…" : v
    return s
  }
  if (typeof v === "number" || typeof v === "boolean") return String(v)
  try {
    const json = JSON.stringify(v)
    return json.length > 80 ? json.slice(0, 80) + "…" : json
  } catch {
    return String(v)
  }
}

function shortUser(uid: string | null): string {
  if (!uid) return "system"
  return uid.slice(0, 8)
}

function formatAuditDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}

function TabHistory({ m }: { m: ModelDetail }) {
  // Параллельно: история по `modeli_osnova` + по каждой вариации `modeli`.
  const variationIds = useMemo(() => m.modeli.map((v) => v.id), [m.modeli])
  const variationLabelById = useMemo(() => {
    const map = new Map<number, string>()
    for (const v of m.modeli) {
      map.set(v.id, v.nazvanie || v.kod)
    }
    return map
  }, [m.modeli])

  const auditQ = useQuery<AuditRowExt[]>({
    queryKey: ["catalog", "audit", m.id, variationIds],
    queryFn: async () => {
      const [osnovaRows, ...variationRows] = await Promise.all([
        fetchAuditFor("modeli_osnova", m.id),
        ...variationIds.map((vid) => fetchAuditFor("modeli", vid)),
      ])
      const out: AuditRowExt[] = []
      for (const row of osnovaRows) {
        out.push({ ...row, source_label: "Модель" })
      }
      variationRows.forEach((rows, idx) => {
        const vid = variationIds[idx]
        const label = variationLabelById.get(vid) ?? String(vid)
        for (const row of rows) {
          out.push({ ...row, source_label: `Вариация (${label})` })
        }
      })
      out.sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
      return out
    },
    staleTime: 30 * 1000,
  })

  if (auditQ.isLoading) {
    return (
      <Section label="История изменений">
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Загружаем историю…
        </div>
      </Section>
    )
  }

  if (auditQ.error) {
    return (
      <Section label="История изменений">
        <div className="text-sm text-red-600">
          Не удалось загрузить историю: {String(auditQ.error)}
        </div>
      </Section>
    )
  }

  const rows = auditQ.data ?? []

  if (rows.length === 0) {
    return (
      <Section
        label="История изменений"
        hint="Все изменения модели и её вариаций. Журнал ведётся автоматически."
      >
        <div className="text-sm text-stone-400 italic py-6 text-center">
          Изменений пока нет.
        </div>
      </Section>
    )
  }

  return (
    <Section
      label="История изменений"
      hint="Все изменения модели и её вариаций. Журнал ведётся автоматически."
    >
      <div className="space-y-2">
        {rows.map((r) => (
          <div
            key={r.id}
            className="border border-stone-200 rounded-md p-3 bg-stone-50"
          >
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span
                className={
                  "px-1.5 py-0.5 rounded border font-medium uppercase tracking-wider " +
                  actionBadgeClass(r.action)
                }
              >
                {r.action}
              </span>
              <span className="font-medium text-stone-800">
                {tableLabel(r.table_name)}
              </span>
              <span className="text-stone-400">·</span>
              <span className="text-stone-600">{r.source_label}</span>
              <span className="text-stone-400">·</span>
              <span className="text-stone-500 tabular-nums">
                {formatAuditDate(r.created_at)}
              </span>
              <span className="text-stone-400">·</span>
              <span
                className="text-stone-500 font-mono"
                title={r.user_id ?? "service_role / system"}
              >
                {shortUser(r.user_id)}
              </span>
            </div>

            {r.action === "INSERT" && (
              <div className="mt-2 text-xs text-stone-600">
                Запись создана (id={r.row_id}).
              </div>
            )}

            {r.action === "DELETE" && r.before && (
              <div className="mt-2 text-xs text-stone-600">
                <div className="text-stone-500 mb-1">
                  Удалено. Снимок до удаления:
                </div>
                <div className="grid grid-cols-1 gap-0.5 font-mono text-[11px] text-stone-700">
                  {Object.entries(r.before)
                    .slice(0, 8)
                    .map(([k, v]) => (
                      <div key={k} className="truncate">
                        <span className="text-stone-500">{k}:</span>{" "}
                        {formatAuditValue(v)}
                      </div>
                    ))}
                  {Object.keys(r.before).length > 8 && (
                    <div className="text-stone-400">
                      … ещё {Object.keys(r.before).length - 8} полей
                    </div>
                  )}
                </div>
              </div>
            )}

            {r.action === "UPDATE" && r.changed && (
              <div className="mt-2 space-y-1 font-mono text-[11px]">
                {Object.entries(r.changed).map(([key, diff]) => (
                  <div key={key} className="flex flex-wrap gap-1 items-baseline">
                    <span className="text-stone-700 font-medium">{key}:</span>
                    <span className="text-red-600 line-through">
                      {formatAuditValue(diff.from)}
                    </span>
                    <span className="text-stone-400">→</span>
                    <span className="text-emerald-700">
                      {formatAuditValue(diff.to)}
                    </span>
                  </div>
                ))}
                {Object.keys(r.changed).length === 0 && (
                  <div className="text-stone-400 italic">
                    {actionLabel(r.action)} (без полевых изменений)
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </Section>
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
  m, attrs, hexByCvet, openColor, kod,
}: {
  m: ModelDetail
  attrs: Atribut[]
  hexByCvet: Map<number, string | null>
  openColor: (colorCode: string) => void
  kod: string
}) {
  // W4.2: state + mutation for "Добавить вариацию" modal.
  const queryClient = useQueryClient()
  const [variationOpen, setVariationOpen] = useState(false)
  const createVariationMut = useMutation({
    mutationFn: (importerId: number) => insertVariation(m.id, importerId),
    onSuccess: () => {
      setVariationOpen(false)
      queryClient.invalidateQueries({ queryKey: ["catalog", "model", kod] })
      queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      queryClient.invalidateQueries({ queryKey: ["matrix-list"] })
    },
  })
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
            onClick={() => setVariationOpen(true)}
            className="text-xs text-stone-700 hover:bg-stone-100 rounded px-2 py-0.5 flex items-center gap-1"
            title="Добавить вариацию (новое юрлицо)"
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
            return (
              <Tooltip key={c.code} text={c.name ? `${c.name} (${c.code})` : c.code}>
                <button
                  type="button"
                  onClick={() => openColor(c.code)}
                  className="flex items-center gap-1.5 bg-stone-50 hover:bg-stone-100 rounded px-1.5 py-1 text-xs"
                >
                  <span
                    className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
                    style={colorSwatchStyle(hex)}
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

      {variationOpen && (
        <VariationModal
          parentKod={m.kod}
          existingVariations={m.modeli.map((v) => ({
            importerId: v.importer_id,
            importerName: v.importer_nazvanie,
            kod: v.kod,
          }))}
          onCancel={() => setVariationOpen(false)}
          onConfirm={(importerId) => createVariationMut.mutate(importerId)}
          pending={createVariationMut.isPending}
          error={createVariationMut.error ? String(createVariationMut.error) : null}
        />
      )}
    </>
  )
}

// ─── W4.2: VariationModal — выбор юрлица для новой вариации ─────────────────

function VariationModal({
  parentKod,
  existingVariations,
  onCancel,
  onConfirm,
  pending,
  error,
}: {
  parentKod: string
  existingVariations: { importerId: number | null; importerName: string | null; kod: string }[]
  onCancel: () => void
  onConfirm: (importerId: number) => void
  pending: boolean
  error: string | null
}) {
  const importeryQ = useQuery({
    queryKey: ["catalog", "importery"],
    queryFn: fetchImportery,
    staleTime: 5 * 60 * 1000,
  })
  const [importerId, setImporterId] = useState<number | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const submit = () => {
    if (importerId == null) {
      setLocalError("Выберите юрлицо")
      return
    }
    setLocalError(null)
    onConfirm(importerId)
  }

  const importery = importeryQ.data ?? []

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
          <div className="font-medium text-stone-900">Создать вариацию</div>
          <button onClick={onCancel} className="p-1 hover:bg-stone-100 rounded">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div className="text-xs text-stone-500">
            Вариация = базовая модель <span className="font-mono">{parentKod}</span> × юрлицо
            (importer). Kod новой вариации будет вида{" "}
            <span className="font-mono">{parentKod}-{existingVariations.length + 1}</span>,
            его можно поправить позже inline.
          </div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-500">
            Юрлицо
          </label>
          <select
            autoFocus
            value={importerId ?? ""}
            onChange={(e) => {
              const val = e.target.value
              setImporterId(val ? Number(val) : null)
              setLocalError(null)
            }}
            className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
          >
            <option value="">— выберите —</option>
            {importery.map((imp) => (
              <option key={imp.id} value={imp.id}>
                {imp.nazvanie}
              </option>
            ))}
          </select>
          {existingVariations.length > 0 && (
            <div className="text-[11px] text-stone-400">
              Уже есть вариации:{" "}
              {existingVariations
                .map((v) => `${v.kod}${v.importerName ? ` (${v.importerName.split(" ")[0]})` : ""}`)
                .join(", ")}
            </div>
          )}
          {(localError || error) && (
            <div className="text-xs text-red-600">{localError ?? error}</div>
          )}
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
            disabled={pending || importeryQ.isLoading}
            className="px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-50"
          >
            {pending ? "Создаём…" : "Создать"}
          </button>
        </div>
      </div>
    </div>
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

  // W5.2: header_image_url хранит storage path (private bucket catalog-assets),
  // отдаваемый в UI только через signed URL. Резолвим тут — TTL 1h.
  const headerImagePath = m.header_image_url ?? null
  const [headerSignedUrl, setHeaderSignedUrl] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    if (!headerImagePath) {
      setHeaderSignedUrl(null)
      return
    }
    void getCatalogAssetSignedUrl(headerImagePath)
      .then((url) => { if (!cancelled) setHeaderSignedUrl(url) })
      .catch(() => { if (!cancelled) setHeaderSignedUrl(null) })
    return () => { cancelled = true }
  }, [headerImagePath])

  const firstHex = firstCvet
    ? (firstCvet.id != null ? hexByCvet.get(firstCvet.id) ?? null : null)
    : null

  return (
    <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4 flex items-center gap-4">
      {/* Icon */}
      <div
        className="w-14 h-14 rounded-lg ring-1 ring-stone-200 shrink-0 overflow-hidden flex items-center justify-center bg-stone-50"
        style={!headerSignedUrl ? colorSwatchStyle(firstHex) : undefined}
      >
        {headerSignedUrl ? (
          <img src={headerSignedUrl} alt="" className="w-full h-full object-cover" />
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
          <StatusBadge statusId={m.status_id} />
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

  // Razmery — общий справочник, нужен для будущих фичей (CRUD размеров, и т.д.).
  // Per-model lineup теперь приходит из junction `modeli_osnova_razmery`
  // через `fetchSizesForModel` в TabDescription (W2.1).
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

  // W6.1: атрибуты категории — из БД (`atributy` + `kategoriya_atributy`).
  // Используется для CardSidebar (Заполненность %, "X/Y атрибутов").
  const sidebarAttrKeysQ = useQuery({
    queryKey: ["catalog", "kategoriya-atributy", model?.kategoriya_id],
    queryFn: () => fetchAttributesForCategory(model!.kategoriya_id as number),
    enabled: model?.kategoriya_id != null,
    staleTime: 5 * 60 * 1000,
  })
  const sidebarAttrs: Atribut[] = sidebarAttrKeysQ.data ?? []

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
      <div className="relative ml-auto w-full max-w-[min(1280px,98vw)] h-full bg-stone-50 border-l border-stone-200 rounded-l-2xl shadow-[-20px_0_40px_rgba(0,0,0,0.08)] flex flex-col overflow-hidden">
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
                { id: "history", label: "История" },
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
                    attrs={sidebarAttrs}
                    hexByCvet={hexByCvet}
                    openColor={openColor}
                    kod={kod}
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
    case "history":     return <TabHistory     m={rest.m} />
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
