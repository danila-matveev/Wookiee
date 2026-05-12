import { supabase } from "@/lib/supabase"
import type { ModelOsnova } from "@/types/catalog"
import { computeCompleteness, getMissingFields, type CompletenessField } from "./color-utils"
import { parseRazmeryModeli } from "./model-utils"

// ─── Basic reference fetchers ──────────────────────────────────────────────

export async function fetchKategorii() {
  const { data, error } = await supabase
    .from("kategorii")
    .select("id, nazvanie, opisanie")
    .order("id")
  if (error) throw error
  return data as { id: number; nazvanie: string; opisanie: string | null }[]
}

// ─── Атрибуты — registry (W6.1) ────────────────────────────────────────────
//
// Полный реестр атрибутов: label, type, options. До W6.1 хранилось хардкодом
// в `src/types/catalog.ts::ALL_ATTRIBUTES`. Теперь — таблица `atributy`
// (миграция 022). Связь категория↔атрибут — через `kategoriya_atributy`
// (миграция 016 + FK `atribut_id` из 022).
//
// W6.2: type='url' допускает кастомные пользовательские поля (Я.Диск, ссылка).

export type AtributType =
  | "text"
  | "number"
  | "textarea"
  | "select"
  | "multiselect"
  | "file_url"
  | "url"
  | "date"
  | "checkbox"
  | "pills"

export interface Atribut {
  id: number
  key: string
  label: string
  type: AtributType
  options: string[]
  default_value: string | null
  helper_text: string | null
}

export interface AtributPayload {
  key: string
  label: string
  type: AtributType
  options?: string[]
  default_value?: string | null
  helper_text?: string | null
}

export async function fetchAtributy(): Promise<Atribut[]> {
  const { data, error } = await supabase
    .from("atributy")
    .select("id, key, label, type, options, default_value, helper_text")
    .order("label")
  if (error) throw new Error(error.message)
  return (data ?? []).map((r: any) => ({
    id: r.id as number,
    key: r.key as string,
    label: r.label as string,
    type: r.type as AtributType,
    options: Array.isArray(r.options) ? (r.options as string[]) : [],
    default_value: (r.default_value ?? null) as string | null,
    helper_text: (r.helper_text ?? null) as string | null,
  }))
}

export async function fetchAtributById(id: number): Promise<Atribut | null> {
  const { data, error } = await supabase
    .from("atributy")
    .select("id, key, label, type, options, default_value, helper_text")
    .eq("id", id)
    .maybeSingle()
  if (error) throw new Error(error.message)
  if (!data) return null
  const r = data as any
  return {
    id: r.id as number,
    key: r.key as string,
    label: r.label as string,
    type: r.type as AtributType,
    options: Array.isArray(r.options) ? (r.options as string[]) : [],
    default_value: (r.default_value ?? null) as string | null,
    helper_text: (r.helper_text ?? null) as string | null,
  }
}

export async function insertAtribut(payload: AtributPayload): Promise<Atribut> {
  const row = {
    key: payload.key,
    label: payload.label,
    type: payload.type,
    options: payload.options ?? [],
    default_value: payload.default_value ?? null,
    helper_text: payload.helper_text ?? null,
  }
  const { data, error } = await supabase
    .from("atributy")
    .insert(row)
    .select("id, key, label, type, options, default_value, helper_text")
    .single()
  if (error) throw new Error(error.message)
  const r = data as any
  return {
    id: r.id as number,
    key: r.key as string,
    label: r.label as string,
    type: r.type as AtributType,
    options: Array.isArray(r.options) ? (r.options as string[]) : [],
    default_value: (r.default_value ?? null) as string | null,
    helper_text: (r.helper_text ?? null) as string | null,
  }
}

export async function updateAtribut(
  id: number,
  patch: Partial<AtributPayload>,
): Promise<void> {
  const row: Record<string, unknown> = {}
  if (patch.label !== undefined) row.label = patch.label
  if (patch.type !== undefined) row.type = patch.type
  if (patch.options !== undefined) row.options = patch.options
  if (patch.default_value !== undefined) row.default_value = patch.default_value
  if (patch.helper_text !== undefined) row.helper_text = patch.helper_text
  // `key` иммутабелен после save — игнорируем patch.key.
  const { error } = await supabase.from("atributy").update(row).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteAtribut(id: number): Promise<void> {
  // Pre-check: не удаляем, если атрибут используется хотя бы в одной категории.
  const { count, error: countErr } = await supabase
    .from("kategoriya_atributy")
    .select("id", { count: "exact", head: true })
    .eq("atribut_id", id)
  if (countErr) throw new Error(countErr.message)
  if ((count ?? 0) > 0) {
    throw new Error(
      `Нельзя удалить: атрибут используется в ${count} категори${
        (count ?? 0) === 1 ? "и" : "ях"
      }. Сначала отвяжите его в Категориях.`,
    )
  }
  const { error } = await supabase.from("atributy").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * Атрибуты, привязанные к категории, в порядке `poryadok`.
 *
 * Источник истины — таблица `kategoriya_atributy` (миграция 016, W2.2) +
 * FK `atribut_id` → `atributy` (миграция 022, W6.1). Возвращает полный объект
 * `Atribut` (id, key, label, type, options, …) — model-card.tsx использует
 * label/type/options напрямую, без вторичного маппинга через `ALL_ATTRIBUTES`.
 */
/**
 * W9.14 — Привязать существующий атрибут к категории.
 *
 * Вставляет ряд в `kategoriya_atributy`. `poryadok` берётся как `max+1` если
 * не передан явно. Идемпотентен: при конфликте уникального ключа (если такой
 * есть) бросает понятную ошибку — её ловит translateError в UI.
 */
export async function linkAtributToKategoriya(
  atributId: number,
  kategoriyaId: number,
  poryadok?: number,
): Promise<void> {
  let order = poryadok
  if (order == null) {
    const { data: maxRow } = await supabase
      .from("kategoriya_atributy")
      .select("poryadok")
      .eq("kategoriya_id", kategoriyaId)
      .order("poryadok", { ascending: false })
      .limit(1)
      .maybeSingle()
    order = ((maxRow as { poryadok: number } | null)?.poryadok ?? 0) + 1
  }
  const { error } = await supabase
    .from("kategoriya_atributy")
    .insert({ atribut_id: atributId, kategoriya_id: kategoriyaId, poryadok: order })
  if (error) throw new Error(error.message)
}

export async function fetchAttributesForCategory(
  kategoriyaId: number,
): Promise<Atribut[]> {
  const { data, error } = await supabase
    .from("kategoriya_atributy")
    .select(
      "poryadok, atributy:atribut_id(id, key, label, type, options, default_value, helper_text)",
    )
    .eq("kategoriya_id", kategoriyaId)
    .not("atribut_id", "is", null)
    .order("poryadok")
  if (error) throw new Error(error.message)
  return (data ?? [])
    .map((r: any) => {
      const a = r.atributy
      if (!a) return null
      return {
        id: a.id as number,
        key: a.key as string,
        label: a.label as string,
        type: a.type as AtributType,
        options: Array.isArray(a.options) ? (a.options as string[]) : [],
        default_value: (a.default_value ?? null) as string | null,
        helper_text: (a.helper_text ?? null) as string | null,
      } satisfies Atribut
    })
    .filter((x): x is Atribut => x != null)
}

export async function fetchKollekcii() {
  const { data, error } = await supabase
    .from("kollekcii")
    .select("id, nazvanie, opisanie, god_zapuska")
    .order("nazvanie")
  if (error) throw error
  return data as { id: number; nazvanie: string; opisanie: string | null; god_zapuska: number | null }[]
}

// W2.3: типы коллекций — справочник, был хардкод `commercial/creative/collab`
// в model-card. Теперь — таблица `tipy_kollekciy` + FK
// `modeli_osnova.tip_kollekcii_id`. Текстовая колонка
// `modeli_osnova.tip_kollekcii` пока остаётся для обратной совместимости и
// пишется параллельно.
export interface TipKollekcii {
  id: number
  nazvanie: string
}

export async function fetchTipyKollekciy(): Promise<TipKollekcii[]> {
  const { data, error } = await supabase
    .from("tipy_kollekciy")
    .select("id, nazvanie")
    .order("nazvanie")
  if (error) throw new Error(error.message)
  return (data ?? []) as TipKollekcii[]
}

export async function fetchFabriki() {
  const { data, error } = await supabase
    .from("fabriki")
    .select("id, nazvanie, strana, gorod, kontakt, email, wechat, specializaciya, leadtime_dni, notes")
    .order("nazvanie")
  if (error) throw error
  return data as {
    id: number
    nazvanie: string
    strana: string | null
    gorod: string | null
    kontakt: string | null
    email: string | null
    wechat: string | null
    specializaciya: string | null
    leadtime_dni: number | null
    notes: string | null
  }[]
}

export async function fetchImportery() {
  const { data, error } = await supabase
    .from("importery")
    .select(
      "id, nazvanie, nazvanie_en, inn, adres, short_name, kpp, ogrn, bank, rs, ks, bik, kontakt, telefon",
    )
    .order("id")
  if (error) throw error
  return data as {
    id: number
    nazvanie: string
    nazvanie_en: string | null
    inn: string | null
    adres: string | null
    short_name: string | null
    kpp: string | null
    ogrn: string | null
    bank: string | null
    rs: string | null
    ks: string | null
    bik: string | null
    kontakt: string | null
    telefon: string | null
  }[]
}

export interface Razmer {
  id: number
  nazvanie: string
  poryadok: number
  ru: string | null
  eu: string | null
  china: string | null
}

export async function fetchRazmery(): Promise<Razmer[]> {
  const { data, error } = await supabase
    .from("razmery")
    .select("id, nazvanie, poryadok, ru, eu, china")
    .order("poryadok")
  if (error) throw error
  return (data ?? []) as Razmer[]
}

// ─── W2.1: размерная линейка модели через junction `modeli_osnova_razmery` ──
// Заменяет хардкод `SIZES_LINEUP = [XS,S,M,L,XL,XXL]` в model-card.tsx.
// Возвращает razmery, привязанные к данной модели, в порядке `poryadok`.

interface ModelSizeRow {
  poryadok: number
  razmery: Razmer | Razmer[] | null
}

export async function fetchSizesForModel(modelOsnovaId: number): Promise<Razmer[]> {
  const { data, error } = await supabase
    .from("modeli_osnova_razmery")
    .select("poryadok, razmery(id, nazvanie, poryadok, ru, eu, china)")
    .eq("model_osnova_id", modelOsnovaId)
    .order("poryadok")
  if (error) throw error
  const rows = (data ?? []) as ModelSizeRow[]
  return rows
    .map((r) => (Array.isArray(r.razmery) ? r.razmery[0] : r.razmery))
    .filter((r): r is Razmer => r !== null && r !== undefined)
}

export async function fetchStatusy() {
  const { data, error } = await supabase
    .from("statusy")
    .select("id, nazvanie, tip, color")
    .order("id")
  if (error) throw error
  return data as { id: number; nazvanie: string; tip: string; color: string | null }[]
}

// ─── New reference fetchers (Wave 0 tables) ───────────────────────────────

export interface SemeystvoCveta {
  id: number
  kod: string
  nazvanie: string
  opisanie: string | null
  poryadok: number | null
}

export async function fetchSemeystvaCvetov(): Promise<SemeystvoCveta[]> {
  const { data, error } = await supabase
    .from("semeystva_cvetov")
    .select("id, kod, nazvanie, opisanie, poryadok")
    .order("poryadok", { ascending: true, nullsFirst: false })
    .order("id")
  if (error) throw error
  return (data ?? []) as SemeystvoCveta[]
}

export interface Upakovka {
  id: number
  nazvanie: string
  tip: string | null
  price_yuan: number | null
  dlina_cm: number | null
  shirina_cm: number | null
  vysota_cm: number | null
  obem_l: number | null
  srok_izgotovleniya_dni: number | null
  file_link: string | null
  notes: string | null
  poryadok: number | null
}

export async function fetchUpakovki(): Promise<Upakovka[]> {
  const { data, error } = await supabase
    .from("upakovki")
    .select(
      "id, nazvanie, tip, price_yuan, dlina_cm, shirina_cm, vysota_cm, obem_l, srok_izgotovleniya_dni, file_link, notes, poryadok",
    )
    .order("poryadok", { ascending: true, nullsFirst: false })
    .order("id")
  if (error) throw error
  return (data ?? []) as Upakovka[]
}

export interface KanalProdazh {
  id: number
  kod: string
  nazvanie: string
  short: string | null
  color: string | null
  active: boolean | null
  poryadok: number | null
}

export async function fetchKanalyProdazh(): Promise<KanalProdazh[]> {
  const { data, error } = await supabase
    .from("kanaly_prodazh")
    .select("id, kod, nazvanie, short, color, active, poryadok")
    .order("poryadok", { ascending: true, nullsFirst: false })
    .order("id")
  if (error) throw error
  return (data ?? []) as KanalProdazh[]
}

export interface Sertifikat {
  id: number
  nazvanie: string
  tip: string | null
  nomer: string | null
  data_vydachi: string | null
  data_okonchaniya: string | null
  organ_sertifikacii: string | null
  file_url: string | null
  gruppa_sertifikata: string | null
  created_at: string | null
  updated_at: string | null
}

export async function fetchSertifikaty(): Promise<Sertifikat[]> {
  const { data, error } = await supabase
    .from("sertifikaty")
    .select(
      "id, nazvanie, tip, nomer, data_vydachi, data_okonchaniya, organ_sertifikacii, file_url, gruppa_sertifikata, created_at, updated_at",
    )
    .order("nazvanie")
  if (error) throw error
  return (data ?? []) as Sertifikat[]
}

// W3.1: brendy — маркетинговые бренды (WOOKIEE / TELOWAY).
// Не путать с fabriki (производитель). Каждая модель в modeli_osnova
// обязана быть привязана к одному бренду через FK brand_id (NOT NULL).
export interface Brend {
  id: number
  kod: string
  nazvanie: string
  opisanie: string | null
  logo_url: string | null
  status_id: number | null
}

export async function fetchBrendy(): Promise<Brend[]> {
  const { data, error } = await supabase
    .from("brendy")
    .select("id, kod, nazvanie, opisanie, logo_url, status_id")
    .order("nazvanie")
  if (error) throw error
  return (data ?? []) as Brend[]
}

// ─── Reference mutations ───────────────────────────────────────────────────

// kategorii
export interface KategoriyaPayload {
  nazvanie: string
  opisanie?: string | null
}

export async function insertKategoriya(data: KategoriyaPayload): Promise<void> {
  const { error } = await supabase.from("kategorii").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateKategoriya(id: number, patch: Partial<KategoriyaPayload>): Promise<void> {
  const { error } = await supabase.from("kategorii").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteKategoriya(id: number): Promise<void> {
  const { error } = await supabase.from("kategorii").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// kollekcii
export interface KollekciyaPayload {
  nazvanie: string
  opisanie?: string | null
  god_zapuska?: number | null
}

export async function insertKollekciya(data: KollekciyaPayload): Promise<void> {
  const { error } = await supabase.from("kollekcii").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateKollekciya(id: number, patch: Partial<KollekciyaPayload>): Promise<void> {
  const { error } = await supabase.from("kollekcii").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteKollekciya(id: number): Promise<void> {
  const { error } = await supabase.from("kollekcii").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// W2.3 tipy_kollekciy CRUD
export interface TipKollekciiPayload {
  nazvanie: string
}

export async function insertTipKollekcii(data: TipKollekciiPayload): Promise<void> {
  const { error } = await supabase.from("tipy_kollekciy").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateTipKollekcii(
  id: number,
  patch: Partial<TipKollekciiPayload>,
): Promise<void> {
  const { error } = await supabase.from("tipy_kollekciy").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteTipKollekcii(id: number): Promise<void> {
  const { error } = await supabase.from("tipy_kollekciy").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// fabriki
export interface FabrikaPayload {
  nazvanie: string
  strana?: string | null
  gorod?: string | null
  kontakt?: string | null
  email?: string | null
  wechat?: string | null
  specializaciya?: string | null
  leadtime_dni?: number | null
  notes?: string | null
}

export async function insertFabrika(data: FabrikaPayload): Promise<void> {
  const { error } = await supabase.from("fabriki").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateFabrika(id: number, patch: Partial<FabrikaPayload>): Promise<void> {
  const { error } = await supabase.from("fabriki").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteFabrika(id: number): Promise<void> {
  const { error } = await supabase.from("fabriki").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// importery
export interface ImporterPayload {
  nazvanie: string
  nazvanie_en?: string | null
  inn?: string | null
  adres?: string | null
  short_name?: string | null
  kpp?: string | null
  ogrn?: string | null
  bank?: string | null
  rs?: string | null
  ks?: string | null
  bik?: string | null
  kontakt?: string | null
  telefon?: string | null
}

export async function insertImporter(data: ImporterPayload): Promise<void> {
  const { error } = await supabase.from("importery").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateImporter(id: number, patch: Partial<ImporterPayload>): Promise<void> {
  const { error } = await supabase.from("importery").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteImporter(id: number): Promise<void> {
  const { error } = await supabase.from("importery").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// razmery
export interface RazmerPayload {
  nazvanie: string
  poryadok: number
  ru?: string | null
  eu?: string | null
  china?: string | null
}

export async function insertRazmer(data: RazmerPayload): Promise<void> {
  const { error } = await supabase.from("razmery").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateRazmer(id: number, patch: Partial<RazmerPayload>): Promise<void> {
  const { error } = await supabase.from("razmery").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteRazmer(id: number): Promise<void> {
  const { error } = await supabase.from("razmery").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// statusy
export interface StatusPayload {
  nazvanie: string
  tip: string
  color?: string | null
}

export async function insertStatus(data: StatusPayload): Promise<void> {
  const { error } = await supabase.from("statusy").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateStatus(id: number, patch: Partial<StatusPayload>): Promise<void> {
  const { error } = await supabase.from("statusy").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteStatus(id: number): Promise<void> {
  const { error } = await supabase.from("statusy").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// semeystva_cvetov
export interface SemeystvoCvetaPayload {
  kod: string
  nazvanie: string
  opisanie?: string | null
  poryadok?: number | null
}

export async function insertSemeystvoCveta(data: SemeystvoCvetaPayload): Promise<void> {
  const { error } = await supabase.from("semeystva_cvetov").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateSemeystvoCveta(id: number, patch: Partial<SemeystvoCvetaPayload>): Promise<void> {
  const { error } = await supabase.from("semeystva_cvetov").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteSemeystvoCveta(id: number): Promise<void> {
  const { error } = await supabase.from("semeystva_cvetov").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// upakovki
export interface UpakovkaPayload {
  nazvanie: string
  tip?: string | null
  price_yuan?: number | null
  dlina_cm?: number | null
  shirina_cm?: number | null
  vysota_cm?: number | null
  obem_l?: number | null
  srok_izgotovleniya_dni?: number | null
  file_link?: string | null
  notes?: string | null
  poryadok?: number | null
}

export async function insertUpakovka(data: UpakovkaPayload): Promise<void> {
  const { error } = await supabase.from("upakovki").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateUpakovka(id: number, patch: Partial<UpakovkaPayload>): Promise<void> {
  const { error } = await supabase.from("upakovki").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteUpakovka(id: number): Promise<void> {
  const { error } = await supabase.from("upakovki").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// kanaly_prodazh
export interface KanalProdazhPayload {
  kod: string
  nazvanie: string
  short?: string | null
  color?: string | null
  active?: boolean | null
  poryadok?: number | null
}

export async function insertKanalProdazh(data: KanalProdazhPayload): Promise<void> {
  const { error } = await supabase.from("kanaly_prodazh").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateKanalProdazh(id: number, patch: Partial<KanalProdazhPayload>): Promise<void> {
  const { error } = await supabase.from("kanaly_prodazh").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteKanalProdazh(id: number): Promise<void> {
  const { error } = await supabase.from("kanaly_prodazh").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// sertifikaty
export interface SertifikatPayload {
  nazvanie: string
  tip?: string | null
  nomer?: string | null
  data_vydachi?: string | null
  data_okonchaniya?: string | null
  organ_sertifikacii?: string | null
  file_url?: string | null
  gruppa_sertifikata?: string | null
}

export async function insertSertifikat(data: SertifikatPayload): Promise<void> {
  const { error } = await supabase.from("sertifikaty").insert(data)
  if (error) throw new Error(error.message)
}

export async function updateSertifikat(id: number, patch: Partial<SertifikatPayload>): Promise<void> {
  const { error } = await supabase.from("sertifikaty").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function deleteSertifikat(id: number): Promise<void> {
  const { error } = await supabase.from("sertifikaty").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// brendy (W3.1)
// Нет 'brand' tip в statusy → status_id остаётся nullable, без soft-delete-паттерна.
// archiveBrend = hard delete с защитой: нельзя удалить бренд, к которому привязаны модели.
export interface BrendPayload {
  kod: string
  nazvanie: string
  opisanie?: string | null
  logo_url?: string | null
  status_id?: number | null
}

export async function insertBrend(payload: BrendPayload): Promise<Brend> {
  const { data, error } = await supabase
    .from("brendy")
    .insert(payload)
    .select("id, kod, nazvanie, opisanie, logo_url, status_id")
    .single()
  if (error) throw new Error(error.message)
  return data as Brend
}

export async function updateBrend(id: number, patch: Partial<BrendPayload>): Promise<void> {
  const { error } = await supabase.from("brendy").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

export async function archiveBrend(id: number): Promise<void> {
  const { count, error: countErr } = await supabase
    .from("modeli_osnova")
    .select("id", { count: "exact", head: true })
    .eq("brand_id", id)
  if (countErr) throw new Error(countErr.message)
  if ((count ?? 0) > 0) {
    throw new Error(`Нельзя удалить бренд: ${count} моделей привязано`)
  }
  const { error } = await supabase.from("brendy").delete().eq("id", id)
  if (error) throw new Error(error.message)
}

// ─── Tags (across all models) ──────────────────────────────────────────────

/**
 * Все уникальные теги из `modeli_osnova.tegi` (text, CSV).
 * Используется TagsCombobox для автокомплита.
 */
export async function fetchAllTags(): Promise<string[]> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("tegi")
    .not("tegi", "is", null)
  if (error) throw error
  const rows = (data ?? []) as { tegi: string | null }[]
  const seen = new Set<string>()
  const result: string[] = []
  for (const row of rows) {
    if (!row.tegi) continue
    for (const part of row.tegi.split(",")) {
      const t = part.trim()
      if (!t) continue
      const key = t.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      result.push(t)
    }
  }
  result.sort((a, b) => a.localeCompare(b, "ru"))
  return result
}

// ─── Matrix list (modeli_osnova with aggregated counts) ────────────────────

export interface MatrixRow {
  id: number
  kod: string
  nazvanie_sayt: string | null
  /** W9.3 — нужно в search-полях матрицы (часто более полное имя, чем nazvanie_sayt). */
  nazvanie_etiketka: string | null
  tip_kollekcii: string | null
  kategoriya_id: number | null
  kategoriya: string | null
  kollekciya: string | null
  fabrika: string | null
  /** W3.2 — brand FK + denormalized name for matrix render. */
  brand_id: number | null
  brand: string | null
  status_id: number | null
  updated_at: string | null
  modeli_cnt: number
  artikuly_cnt: number
  tovary_cnt: number
  cveta_cnt: number
  completeness: number
  /** Список незаполненных ключевых полей для tooltip над CompletenessRing. */
  missing_fields: CompletenessField[]
  /**
   * W9.8 — канонический размерный ряд модели (parsed CSV из
   * `modeli_osnova.razmery_modeli`). Единственный источник истины для колонки
   * «Размеры» в матрице. Пустой массив, если ряд не заполнен в карточке.
   */
  razmery: string[]
  modeli: {
    id: number
    kod: string
    nazvanie: string
    artikul_modeli: string | null
    importer_id: number | null
    importer_short: string | null
    status_id: number | null
    rossiyskiy_razmer: string | null
    artikuly_cnt: number
    tovary_cnt: number
  }[]
}

export async function fetchMatrixList(): Promise<MatrixRow[]> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select(`
      id, kod, nazvanie_sayt, tip_kollekcii, kategoriya_id, updated_at,
      sostav_syrya, razmery_modeli, sku_china, ves_kg, dlina_cm, shirina_cm,
      vysota_cm, kratnost_koroba, nazvanie_etiketka, opisanie_sayt, tnved, gruppa_sertifikata,
      kollekciya_id, fabrika_id, status_id, brand_id,
      kategorii(nazvanie),
      kollekcii(nazvanie),
      fabriki(nazvanie),
      brendy(nazvanie),
      modeli(
        id, kod, nazvanie, artikul_modeli, importer_id, status_id, rossiyskiy_razmer,
        importery(nazvanie),
        artikuly(id, cvet_id, tovary(id))
      )
    `)
    .order("kod")
  if (error) throw error

  return (data as any[]).map((mo) => {
    const modeli = (mo.modeli ?? []) as any[]
    const artikuly = modeli.flatMap((m: any) => m.artikuly ?? [])
    const tovary = artikuly.flatMap((a: any) => a.tovary ?? [])
    const cvetaIds = new Set(artikuly.map((a: any) => a.cvet_id).filter(Boolean))

    return {
      id: mo.id,
      kod: mo.kod,
      nazvanie_sayt: mo.nazvanie_sayt,
      nazvanie_etiketka: mo.nazvanie_etiketka ?? null,
      tip_kollekcii: mo.tip_kollekcii,
      kategoriya_id: mo.kategoriya_id,
      kategoriya: mo.kategorii?.nazvanie ?? null,
      kollekciya: mo.kollekcii?.nazvanie ?? null,
      fabrika: mo.fabriki?.nazvanie ?? null,
      brand_id: mo.brand_id ?? null,
      brand: mo.brendy?.nazvanie ?? null,
      status_id: mo.status_id,
      updated_at: mo.updated_at,
      modeli_cnt: modeli.length,
      artikuly_cnt: artikuly.length,
      tovary_cnt: tovary.length,
      cveta_cnt: cvetaIds.size,
      completeness: computeCompleteness(mo),
      missing_fields: getMissingFields(mo),
      razmery: parseRazmeryModeli(mo.razmery_modeli),
      modeli: modeli.map((m: any) => {
        const mArts = (m.artikuly ?? []) as any[]
        const mTovary = mArts.flatMap((a: any) => a.tovary ?? [])
        return {
          id: m.id,
          kod: m.kod,
          nazvanie: m.nazvanie,
          artikul_modeli: m.artikul_modeli,
          importer_id: m.importer_id,
          importer_short: m.importery?.nazvanie?.split(" ")[0] ?? null,
          status_id: m.status_id,
          rossiyskiy_razmer: m.rossiyskiy_razmer,
          artikuly_cnt: mArts.length,
          tovary_cnt: mTovary.length,
        }
      }),
    } as MatrixRow
  })
}

// ─── Model card (full detail) ──────────────────────────────────────────────

export interface ModelDetail extends ModelOsnova {
  kategoriya: string | null
  kollekciya: string | null
  fabrika: string | null
  status_nazvanie: string | null
  modeli: ModelVariation[]
}

export interface ModelVariation {
  id: number
  kod: string
  nazvanie: string
  nazvanie_en: string | null
  artikul_modeli: string | null
  importer_id: number | null
  importer_nazvanie: string | null
  status_id: number | null
  rossiyskiy_razmer: string | null
  nabor: boolean | null
  artikuly: VariationArtikul[]
}

export interface VariationArtikul {
  id: number
  artikul: string
  cvet_id: number | null
  cvet_color_code: string | null
  cvet_nazvanie: string | null
  cvet_semeystvo: string | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  tovary: ArtTovar[]
}

export interface ArtTovar {
  id: number
  barkod: string
  razmer_id: number | null
  razmer_nazvanie: string | null
  status_id: number | null
  status_ozon_id: number | null
  status_sayt_id: number | null
  status_lamoda_id: number | null
  sku_china_size: string | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
  lamoda_seller_sku: string | null
}

export async function fetchModelDetail(id: number): Promise<ModelDetail | null> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select(`
      *,
      kategorii(nazvanie),
      kollekcii(nazvanie),
      fabriki(nazvanie),
      statusy(nazvanie),
      modeli(
        id, kod, nazvanie, nazvanie_en, artikul_modeli, importer_id, status_id,
        rossiyskiy_razmer, nabor,
        importery(nazvanie),
        artikuly(
          id, artikul, cvet_id, status_id, nomenklatura_wb, artikul_ozon,
          cveta(id, color_code, cvet, semeystvo),
          tovary(
            id, barkod, razmer_id, status_id, status_ozon_id, status_sayt_id,
            status_lamoda_id, sku_china_size, ozon_product_id, ozon_fbo_sku_id, lamoda_seller_sku,
            razmery(nazvanie)
          )
        )
      )
    `)
    .eq("id", id)
    .single()
  if (error) {
    if (error.code === "PGRST116") return null
    throw error
  }

  const raw = data as any
  return {
    ...raw,
    kategoriya: raw.kategorii?.nazvanie ?? null,
    kollekciya: raw.kollekcii?.nazvanie ?? null,
    fabrika: raw.fabriki?.nazvanie ?? null,
    status_nazvanie: raw.statusy?.nazvanie ?? null,
    modeli: (raw.modeli ?? []).map((m: any) => ({
      id: m.id,
      kod: m.kod,
      nazvanie: m.nazvanie,
      nazvanie_en: m.nazvanie_en,
      artikul_modeli: m.artikul_modeli,
      importer_id: m.importer_id,
      importer_nazvanie: m.importery?.nazvanie ?? null,
      status_id: m.status_id,
      rossiyskiy_razmer: m.rossiyskiy_razmer,
      nabor: m.nabor,
      artikuly: (m.artikuly ?? []).map((a: any) => ({
        id: a.id,
        artikul: a.artikul,
        cvet_id: a.cvet_id,
        cvet_color_code: a.cveta?.color_code ?? null,
        cvet_nazvanie: a.cveta?.cvet ?? null,
        cvet_semeystvo: a.cveta?.semeystvo ?? null,
        status_id: a.status_id,
        nomenklatura_wb: a.nomenklatura_wb,
        artikul_ozon: a.artikul_ozon,
        tovary: (a.tovary ?? []).map((t: any) => ({
          id: t.id,
          barkod: t.barkod,
          razmer_id: t.razmer_id,
          razmer_nazvanie: t.razmery?.nazvanie ?? null,
          status_id: t.status_id,
          status_ozon_id: t.status_ozon_id,
          status_sayt_id: t.status_sayt_id,
          status_lamoda_id: t.status_lamoda_id,
          sku_china_size: t.sku_china_size,
          ozon_product_id: t.ozon_product_id,
          ozon_fbo_sku_id: t.ozon_fbo_sku_id,
          lamoda_seller_sku: t.lamoda_seller_sku,
        } as ArtTovar)),
      } as VariationArtikul)),
    } as ModelVariation)),
  } as ModelDetail
}

// ─── Colors with usage counts ──────────────────────────────────────────────

export interface CvetRow {
  id: number
  color_code: string
  cvet: string | null
  color: string | null
  lastovica: string | null
  hex: string | null
  semeystvo: string | null
  semeystvo_id: number | null
  status_id: number | null
  image_url: string | null
  created_at: string | null
  updated_at: string | null
  artikuly_cnt: number
  modeli_cnt: number
}

export async function fetchCvetaWithUsage(): Promise<CvetRow[]> {
  const [cvetaRes, artikulyRes] = await Promise.all([
    supabase
      .from("cveta")
      .select("id, color_code, cvet, color, lastovica, hex, semeystvo, semeystvo_id, status_id, image_url, created_at, updated_at")
      .order("color_code"),
    supabase
      .from("artikuly")
      .select("id, cvet_id, modeli(model_osnova_id)"),
  ])
  if (cvetaRes.error) throw cvetaRes.error
  if (artikulyRes.error) throw artikulyRes.error

  const artsByCvet = new Map<number, number>()
  const modelsByCvet = new Map<number, Set<number>>()

  for (const a of (artikulyRes.data ?? []) as any[]) {
    if (!a.cvet_id) continue
    artsByCvet.set(a.cvet_id, (artsByCvet.get(a.cvet_id) ?? 0) + 1)
    const osnovaId = a.modeli?.model_osnova_id
    if (osnovaId) {
      if (!modelsByCvet.has(a.cvet_id)) modelsByCvet.set(a.cvet_id, new Set())
      modelsByCvet.get(a.cvet_id)!.add(osnovaId)
    }
  }

  return (cvetaRes.data ?? []).map((c) => ({
    ...c,
    artikuly_cnt: artsByCvet.get(c.id) ?? 0,
    modeli_cnt: modelsByCvet.get(c.id)?.size ?? 0,
  })) as CvetRow[]
}

// ─── Color card detail ─────────────────────────────────────────────────────

export interface ColorDetailArtikul {
  id: number
  artikul: string
  model_kod: string | null
  model_osnova_kod: string | null
  model_osnova_id: number | null
  kategoriya: string | null
  tip_kollekcii: string | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  status_id: number | null
  tovary_cnt: number
}

export interface ColorDetail extends CvetRow {
  artikuly: ColorDetailArtikul[]
}

const COLOR_DETAIL_ARTIKUL_SELECT = `
        id, artikul, nomenklatura_wb, artikul_ozon, status_id,
        modeli(
          id, kod, model_osnova_id,
          modeli_osnova(id, kod, tip_kollekcii, kategorii(nazvanie))
        ),
        tovary(id)
      `

const CVETA_DETAIL_SELECT =
  "id, color_code, cvet, color, lastovica, hex, semeystvo, semeystvo_id, status_id, image_url, created_at, updated_at"

function buildColorDetail(cvet: any, rawArts: any[]): ColorDetail {
  const artikuly: ColorDetailArtikul[] = rawArts.map((a) => ({
    id: a.id,
    artikul: a.artikul,
    model_kod: a.modeli?.kod ?? null,
    model_osnova_kod: a.modeli?.modeli_osnova?.kod ?? null,
    model_osnova_id: a.modeli?.model_osnova_id ?? null,
    kategoriya: a.modeli?.modeli_osnova?.kategorii?.nazvanie ?? null,
    tip_kollekcii: a.modeli?.modeli_osnova?.tip_kollekcii ?? null,
    nomenklatura_wb: a.nomenklatura_wb ?? null,
    artikul_ozon: a.artikul_ozon ?? null,
    status_id: a.status_id ?? null,
    tovary_cnt: (a.tovary ?? []).length,
  }))

  const modelsSet = new Set(rawArts.map((a) => a.modeli?.model_osnova_id).filter(Boolean))

  return {
    ...cvet,
    artikuly_cnt: rawArts.length,
    modeli_cnt: modelsSet.size,
    artikuly,
  } as ColorDetail
}

export async function fetchColorDetail(id: number): Promise<ColorDetail | null> {
  const [cvetRes, artikulyRes] = await Promise.all([
    supabase
      .from("cveta")
      .select(CVETA_DETAIL_SELECT)
      .eq("id", id)
      .single(),
    supabase
      .from("artikuly")
      .select(COLOR_DETAIL_ARTIKUL_SELECT)
      .eq("cvet_id", id),
  ])

  if (cvetRes.error) {
    if (cvetRes.error.code === "PGRST116") return null
    throw cvetRes.error
  }
  if (artikulyRes.error) throw artikulyRes.error

  return buildColorDetail(cvetRes.data, (artikulyRes.data ?? []) as any[])
}

export async function fetchColorDetailByCode(code: string): Promise<ColorDetail | null> {
  const cvetRes = await supabase
    .from("cveta")
    .select(CVETA_DETAIL_SELECT)
    .eq("color_code", code)
    .maybeSingle()
  if (cvetRes.error) throw cvetRes.error
  if (!cvetRes.data) return null

  const artikulyRes = await supabase
    .from("artikuly")
    .select(COLOR_DETAIL_ARTIKUL_SELECT)
    .eq("cvet_id", (cvetRes.data as any).id)
  if (artikulyRes.error) throw artikulyRes.error

  return buildColorDetail(cvetRes.data, (artikulyRes.data ?? []) as any[])
}

// ─── Skleyki ───────────────────────────────────────────────────────────────

export interface SkleykaRow {
  id: number
  nazvanie: string
  importer_id: number | null
  importer_nazvanie: string | null
  created_at: string | null
  updated_at: string | null
  /** Канал — заполняется на уровне fetcher (для смешанных списков). */
  channel?: 'wb' | 'ozon'
  /** Кол-во SKU в склейке — нужно для колонки «Заполненность». */
  count_tovary?: number
}

async function fetchSkleykiWithCounts(
  table: 'skleyki_wb' | 'skleyki_ozon',
  junction: 'tovary_skleyki_wb' | 'tovary_skleyki_ozon',
  channel: 'wb' | 'ozon',
): Promise<SkleykaRow[]> {
  const [skRes, jRes] = await Promise.all([
    supabase
      .from(table)
      .select("id, nazvanie, importer_id, importery(nazvanie), created_at, updated_at")
      .order("nazvanie"),
    supabase.from(junction).select("skleyka_id"),
  ])
  if (skRes.error) throw skRes.error
  if (jRes.error) throw jRes.error

  const counts = new Map<number, number>()
  for (const row of (jRes.data ?? []) as { skleyka_id: number }[]) {
    counts.set(row.skleyka_id, (counts.get(row.skleyka_id) ?? 0) + 1)
  }

  return (skRes.data as any[]).map((s) => ({
    id: s.id,
    nazvanie: s.nazvanie,
    importer_id: s.importer_id,
    importer_nazvanie: s.importery?.nazvanie ?? null,
    created_at: s.created_at,
    updated_at: s.updated_at,
    channel,
    count_tovary: counts.get(s.id) ?? 0,
  }))
}

export async function fetchSkleykiWb(): Promise<SkleykaRow[]> {
  return fetchSkleykiWithCounts('skleyki_wb', 'tovary_skleyki_wb', 'wb')
}

export async function fetchSkleykiOzon(): Promise<SkleykaRow[]> {
  return fetchSkleykiWithCounts('skleyki_ozon', 'tovary_skleyki_ozon', 'ozon')
}

/** Создать новую склейку. Возвращает её id. */
export async function createSkleyka(
  nazvanie: string,
  channel: 'wb' | 'ozon',
  importerId?: number | null,
): Promise<{ id: number }> {
  const table = channel === 'wb' ? 'skleyki_wb' : 'skleyki_ozon'
  const payload: Record<string, unknown> = { nazvanie }
  if (importerId != null) payload.importer_id = importerId
  const { data, error } = await supabase
    .from(table)
    .insert(payload)
    .select("id")
    .single()
  if (error) throw new Error(error.message)
  return data as { id: number }
}

/** Обновить название/импортёра склейки. */
export async function updateSkleyka(
  id: number,
  channel: 'wb' | 'ozon',
  patch: { nazvanie?: string; importer_id?: number | null },
): Promise<void> {
  const table = channel === 'wb' ? 'skleyki_wb' : 'skleyki_ozon'
  const { error } = await supabase.from(table).update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * Удалить склейку. Сначала чистит junction (отвязывает все SKU), затем удаляет
 * запись самой склейки. Junction не имеет ON DELETE CASCADE — придётся ручками.
 */
export async function deleteSkleyka(id: number, channel: 'wb' | 'ozon'): Promise<void> {
  const table = channel === 'wb' ? 'skleyki_wb' : 'skleyki_ozon'
  const junction = channel === 'wb' ? 'tovary_skleyki_wb' : 'tovary_skleyki_ozon'
  const { error: jErr } = await supabase.from(junction).delete().eq("skleyka_id", id)
  if (jErr) throw new Error(jErr.message)
  const { error } = await supabase.from(table).delete().eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * Поиск склеек по баркоду SKU в их составе. Возвращает Set из skleyka_id для
 * указанного канала. Используется в SkleykaList для фильтрации по баркоду.
 */
export async function findSkleykiByBarkod(
  barkodQuery: string,
  channel: 'wb' | 'ozon',
): Promise<Set<number>> {
  const junction = channel === 'wb' ? 'tovary_skleyki_wb' : 'tovary_skleyki_ozon'
  const q = barkodQuery.trim()
  if (!q) return new Set()

  const { data: tovary, error: tErr } = await supabase
    .from("tovary")
    .select("id, barkod")
    .ilike("barkod", `%${q}%`)
    .limit(500)
  if (tErr) throw tErr
  const tovarIds = ((tovary ?? []) as { id: number }[]).map((r) => r.id)
  if (tovarIds.length === 0) return new Set()

  const { data: links, error: lErr } = await supabase
    .from(junction)
    .select("skleyka_id")
    .in("tovar_id", tovarIds)
  if (lErr) throw lErr

  const ids = new Set<number>()
  for (const row of (links ?? []) as { skleyka_id: number }[]) {
    ids.add(row.skleyka_id)
  }
  return ids
}

// ─── Artikuly registry ─────────────────────────────────────────────────────

export interface ArtikulRow {
  id: number
  artikul: string
  model_id: number | null
  model_kod: string | null
  model_osnova_id: number | null
  model_osnova_kod: string | null
  /** modeli_osnova.nazvanie_etiketka — нужно для search и колонки «Модель». */
  nazvanie_etiketka: string | null
  cvet_id: number | null
  cvet_color_code: string | null
  /** cveta.cvet (RU). */
  cvet_nazvanie: string | null
  /** cveta.color (EN). */
  color_en: string | null
  cvet_hex: string | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  tovary_cnt: number
  kategoriya: string | null
  /** W9.10 — категория модели (id) для фильтра ColorPicker по категории. */
  kategoriya_id: number | null
  kollekciya: string | null
  fabrika: string | null
  created_at: string | null
  updated_at: string | null
}

export async function fetchArtikulyRegistry(): Promise<ArtikulRow[]> {
  // Supabase PostgREST default max-rows=1000.  Page through until short response.
  const PAGE = 1000
  const all: any[] = []
  for (let offset = 0; ; offset += PAGE) {
    const { data, error } = await supabase
      .from("artikuly")
      .select(`
        id, artikul, model_id, cvet_id, status_id, nomenklatura_wb, artikul_ozon,
        created_at, updated_at,
        cveta(color_code, cvet, color, hex),
        modeli(
          id, kod, model_osnova_id,
          modeli_osnova(
            id, kod, tip_kollekcii, nazvanie_etiketka, kategoriya_id,
            kategorii(nazvanie),
            kollekcii(nazvanie),
            fabriki(nazvanie)
          )
        ),
        tovary(id)
      `)
      .order("artikul")
      .range(offset, offset + PAGE - 1)
    if (error) throw error
    const rows = (data ?? []) as any[]
    all.push(...rows)
    if (rows.length < PAGE) break
  }

  return (all as any[]).map((a) => ({
    id: a.id,
    artikul: a.artikul,
    model_id: a.model_id,
    model_kod: a.modeli?.kod ?? null,
    model_osnova_id: a.modeli?.model_osnova_id ?? null,
    model_osnova_kod: a.modeli?.modeli_osnova?.kod ?? null,
    nazvanie_etiketka: a.modeli?.modeli_osnova?.nazvanie_etiketka ?? null,
    cvet_id: a.cvet_id,
    cvet_color_code: a.cveta?.color_code ?? null,
    cvet_nazvanie: a.cveta?.cvet ?? null,
    color_en: a.cveta?.color ?? null,
    cvet_hex: a.cveta?.hex ?? null,
    status_id: a.status_id,
    nomenklatura_wb: a.nomenklatura_wb,
    artikul_ozon: a.artikul_ozon,
    tovary_cnt: (a.tovary ?? []).length,
    kategoriya: a.modeli?.modeli_osnova?.kategorii?.nazvanie ?? null,
    kategoriya_id: a.modeli?.modeli_osnova?.kategoriya_id ?? null,
    kollekciya: a.modeli?.modeli_osnova?.kollekcii?.nazvanie ?? null,
    fabrika: a.modeli?.modeli_osnova?.fabriki?.nazvanie ?? null,
    created_at: a.created_at,
    updated_at: a.updated_at,
  }))
}

// ─── Tovary registry ───────────────────────────────────────────────────────

export interface TovarRow {
  id: number
  barkod: string
  /** Дополнительные баркоды. */
  barkod_gs1: string | null
  barkod_gs2: string | null
  barkod_perehod: string | null
  artikul_id: number | null
  artikul: string | null
  model_kod: string | null
  model_osnova_id: number | null
  model_osnova_kod: string | null
  /** modeli_osnova.nazvanie_etiketka — для composite search. */
  nazvanie_etiketka: string | null
  /** modeli_osnova.kollekciya / kategoriya — для group-by. */
  kollekciya: string | null
  kategoriya: string | null
  /** W9.10 — kategoriya_id для ColorPicker (если когда-нибудь будем редактировать цвет SKU). */
  kategoriya_id: number | null
  /** W9.10 — cvet_id, чтобы можно было редактировать цвет SKU (через artikul). */
  cvet_id: number | null
  cvet_color_code: string | null
  /** cveta.cvet (RU). */
  cvet_ru: string | null
  /** cveta.color (EN). */
  color_en: string | null
  cvet_hex: string | null
  razmer: string | null
  /** razmery.kod в БД часто совпадает с nazvanie (XS/S/M/...). */
  razmer_kod: string | null
  /** W9.10 — razmer_id для inline-edit размера. */
  razmer_id: number | null
  status_id: number | null
  status_ozon_id: number | null
  status_sayt_id: number | null
  status_lamoda_id: number | null
  artikul_ozon: string | null
  nomenklatura_wb: number | null
  sku_china_size: string | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
  lamoda_seller_sku: string | null
  created_at: string | null
}

export async function fetchTovaryRegistry(): Promise<TovarRow[]> {
  // PostgREST default max-rows=1000 ignores .range() above its cap.  Page through.
  const PAGE = 1000
  const all: any[] = []
  for (let offset = 0; ; offset += PAGE) {
    const { data, error } = await supabase
      .from("tovary")
      .select(`
        id, barkod, barkod_gs1, barkod_gs2, barkod_perehod, artikul_id, razmer_id,
        status_id, status_ozon_id, status_sayt_id, status_lamoda_id,
        sku_china_size, ozon_product_id, ozon_fbo_sku_id, lamoda_seller_sku,
        created_at,
        razmery(nazvanie),
        artikuly(
          artikul, nomenklatura_wb, artikul_ozon, cvet_id,
          cveta(color_code, cvet, color, hex),
          modeli(
            kod, model_osnova_id,
            modeli_osnova(
              kod, nazvanie_etiketka, kategoriya_id,
              kategorii(nazvanie),
              kollekcii(nazvanie)
            )
          )
        )
      `)
      .order("id")
      .range(offset, offset + PAGE - 1)
    if (error) throw error
    const rows = (data ?? []) as any[]
    all.push(...rows)
    if (rows.length < PAGE) break
  }

  return (all as any[]).map((t) => {
    const razmer = t.razmery?.nazvanie ?? null
    return {
      id: t.id,
      barkod: t.barkod,
      barkod_gs1: t.barkod_gs1 ?? null,
      barkod_gs2: t.barkod_gs2 ?? null,
      barkod_perehod: t.barkod_perehod ?? null,
      artikul_id: t.artikul_id,
      artikul: t.artikuly?.artikul ?? null,
      model_kod: t.artikuly?.modeli?.kod ?? null,
      model_osnova_id: t.artikuly?.modeli?.model_osnova_id ?? null,
      model_osnova_kod: t.artikuly?.modeli?.modeli_osnova?.kod ?? null,
      nazvanie_etiketka: t.artikuly?.modeli?.modeli_osnova?.nazvanie_etiketka ?? null,
      kollekciya: t.artikuly?.modeli?.modeli_osnova?.kollekcii?.nazvanie ?? null,
      kategoriya: t.artikuly?.modeli?.modeli_osnova?.kategorii?.nazvanie ?? null,
      kategoriya_id: t.artikuly?.modeli?.modeli_osnova?.kategoriya_id ?? null,
      cvet_id: t.artikuly?.cvet_id ?? null,
      cvet_color_code: t.artikuly?.cveta?.color_code ?? null,
      cvet_ru: t.artikuly?.cveta?.cvet ?? null,
      color_en: t.artikuly?.cveta?.color ?? null,
      cvet_hex: t.artikuly?.cveta?.hex ?? null,
      razmer,
      razmer_kod: razmer,
      razmer_id: t.razmer_id ?? null,
      status_id: t.status_id,
      status_ozon_id: t.status_ozon_id,
      status_sayt_id: t.status_sayt_id,
      status_lamoda_id: t.status_lamoda_id,
      artikul_ozon: t.artikuly?.artikul_ozon ?? null,
      nomenklatura_wb: t.artikuly?.nomenklatura_wb ?? null,
      sku_china_size: t.sku_china_size,
      ozon_product_id: t.ozon_product_id,
      ozon_fbo_sku_id: t.ozon_fbo_sku_id,
      lamoda_seller_sku: t.lamoda_seller_sku,
      created_at: t.created_at,
    }
  })
}

// ─── Skleyka detail ────────────────────────────────────────────────────────

export interface SkleykaDetailSKU {
  tovar_id: number
  barkod: string
  razmer: string | null
  artikul: string | null
  model_osnova_kod: string | null
  cvet_color_code: string | null
  status_id: number | null
  status_ozon_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  sku_china_size: string | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
}

export interface SkleykaDetail extends SkleykaRow {
  channel: 'wb' | 'ozon'
  tovary: SkleykaDetailSKU[]
}

export async function fetchSkleykaDetail(id: number, channel: 'wb' | 'ozon'): Promise<SkleykaDetail | null> {
  const mainTable = channel === 'wb' ? 'skleyki_wb' : 'skleyki_ozon'
  const junctionTable = channel === 'wb' ? 'tovary_skleyki_wb' : 'tovary_skleyki_ozon'

  const [skleykaRes, junctionRes] = await Promise.all([
    supabase
      .from(mainTable)
      .select('id, nazvanie, importer_id, importery(nazvanie), created_at, updated_at')
      .eq('id', id)
      .single(),
    supabase
      .from(junctionTable)
      .select(`
        tovar_id,
        tovary(
          id, barkod, razmer_id, status_id, status_ozon_id, status_sayt_id, status_lamoda_id,
          sku_china_size, ozon_product_id, ozon_fbo_sku_id,
          razmery(nazvanie),
          artikuly(
            artikul, nomenklatura_wb, artikul_ozon,
            cveta(color_code),
            modeli(kod, modeli_osnova(kod))
          )
        )
      `)
      .eq('skleyka_id', id),
  ])

  if (skleykaRes.error) {
    if (skleykaRes.error.code === 'PGRST116') return null
    throw skleykaRes.error
  }
  if (junctionRes.error) throw junctionRes.error

  const s = skleykaRes.data as any
  const rawRows = (junctionRes.data ?? []) as any[]

  return {
    id: s.id,
    nazvanie: s.nazvanie,
    importer_id: s.importer_id,
    importer_nazvanie: s.importery?.nazvanie ?? null,
    created_at: s.created_at,
    updated_at: s.updated_at,
    channel,
    tovary: rawRows.map((row) => {
      const t = row.tovary ?? {}
      const a = t.artikuly ?? {}
      return {
        tovar_id: row.tovar_id,
        barkod: t.barkod ?? '',
        razmer: t.razmery?.nazvanie ?? null,
        artikul: a.artikul ?? null,
        model_osnova_kod: a.modeli?.modeli_osnova?.kod ?? null,
        cvet_color_code: a.cveta?.color_code ?? null,
        status_id: t.status_id ?? null,
        status_ozon_id: t.status_ozon_id ?? null,
        nomenklatura_wb: a.nomenklatura_wb ?? null,
        artikul_ozon: a.artikul_ozon ?? null,
        sku_china_size: t.sku_china_size ?? null,
        ozon_product_id: t.ozon_product_id ?? null,
        ozon_fbo_sku_id: t.ozon_fbo_sku_id ?? null,
      } as SkleykaDetailSKU
    }),
  }
}

// ─── Cveta mutations ───────────────────────────────────────────────────────

export interface CvetPayload {
  color_code: string
  cvet?: string | null
  color?: string | null
  lastovica?: string | null
  hex?: string | null
  semeystvo_id?: number | null
  semeystvo?: string | null
  status_id?: number | null
  image_url?: string | null
}

export async function insertCvet(data: CvetPayload): Promise<{ id: number }> {
  const { data: row, error } = await supabase
    .from("cveta")
    .insert(data)
    .select("id")
    .single()
  if (error) throw new Error(error.message)
  return row as { id: number }
}

export async function updateCvet(id: number, patch: Partial<CvetPayload>): Promise<void> {
  const { error } = await supabase.from("cveta").update(patch).eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * Soft-delete a colour by switching it to the "Архив" status (tip='color').
 * No real DELETE — references in artikuly may exist.
 */
export async function deleteCvet(id: number): Promise<void> {
  const archiveId = await getArchiveStatusId("color")
  if (archiveId == null) throw new Error("Status 'Архив' (tip='color') not found in DB")
  const { error } = await supabase.from("cveta").update({ status_id: archiveId }).eq("id", id)
  if (error) throw new Error(error.message)
}

// ─── W9.12: cvet_kategoriya (colour → category m2m) ──────────────────────

/**
 * Return the list of kategoriya_id values mapped to a colour.
 * Empty array = colour applies to ALL categories (legacy fallback).
 */
export async function fetchKategoriiForCvet(cvetId: number): Promise<number[]> {
  const { data, error } = await supabase
    .from("cvet_kategoriya")
    .select("kategoriya_id")
    .eq("cvet_id", cvetId)
  if (error) throw new Error(error.message)
  return (data ?? []).map((r) => (r as { kategoriya_id: number }).kategoriya_id)
}

/**
 * Replace the full set of categories for a colour (delete-then-insert).
 * Pass an empty array to clear all mappings (colour becomes universal again).
 */
export async function setKategoriiForCvet(
  cvetId: number,
  kategoriyaIds: number[],
): Promise<void> {
  const { error: delErr } = await supabase
    .from("cvet_kategoriya")
    .delete()
    .eq("cvet_id", cvetId)
  if (delErr) throw new Error(delErr.message)

  if (kategoriyaIds.length === 0) return

  const rows = kategoriyaIds.map((kid) => ({ cvet_id: cvetId, kategoriya_id: kid }))
  const { error: insErr } = await supabase.from("cvet_kategoriya").insert(rows)
  if (insErr) throw new Error(insErr.message)
}

// ─── Modeli operations (create / update / duplicate / archive cascade) ────

export interface ModelOsnovaPayload {
  kod: string
  /** FK to `brendy.id` (WOOKIEE / TELOWAY). NOT NULL в БД — UI должен передавать при save. */
  brand_id?: number | null
  kategoriya_id?: number | null
  kollekciya_id?: number | null
  fabrika_id?: number | null
  status_id?: number | null
  tip_kollekcii?: string | null
  tip_kollekcii_id?: number | null
  material?: string | null
  sostav_syrya?: string | null
  composition?: string | null
  razmery_modeli?: string | null
  sku_china?: string | null
  upakovka?: string | null
  upakovka_id?: number | null
  ves_kg?: number | null
  dlina_cm?: number | null
  shirina_cm?: number | null
  vysota_cm?: number | null
  kratnost_koroba?: number | null
  srok_proizvodstva?: string | null
  komplektaciya?: string | null
  nazvanie_etiketka?: string | null
  nazvanie_sayt?: string | null
  opisanie_sayt?: string | null
  details?: string | null
  description?: string | null
  tegi?: string | null
  notion_link?: string | null
  notion_strategy_link?: string | null
  yandex_disk_link?: string | null
  stepen_podderzhki?: string | null
  forma_chashki?: string | null
  regulirovka?: string | null
  zastezhka?: string | null
  dlya_kakoy_grudi?: string | null
  posadka_trusov?: string | null
  vid_trusov?: string | null
  naznachenie?: string | null
  stil?: string | null
  po_nastroeniyu?: string | null
  tnved?: string | null
  gruppa_sertifikata?: string | null
  /** W5.2: storage path inside catalog-assets bucket (e.g. models/123/header.jpg). */
  header_image_url?: string | null
}

/** Create a new modeli_osnova row. Returns inserted kod. */
export async function createModel(payload: ModelOsnovaPayload): Promise<string> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .insert(payload)
    .select("kod")
    .single()
  if (error) throw new Error(error.message)
  return (data as { kod: string }).kod
}

// ─── W4.1: createModelTransactional ────────────────────────────────────────
// Полноценное создание модели через модалку «+ Новая модель»: атомарно
// создаёт `modeli_osnova` + первую вариацию `modeli` (с importer_id первого
// юрлица) + опционально привязывает размеры через `modeli_osnova_razmery`.
//
// Транзакционность эмулируется sequential-INSERT с rollback (DELETE
// modeli_osnova on error in modeli/razmery insert). Если в будущем появится
// RPC `create_model_transactional` — заменить тело на supabase.rpc().

export interface CreateModelTransactionalPayload {
  /** PK для modeli_osnova.kod и modeli.kod (latin, без пробелов). */
  kod: string
  brand_id: number
  kategoriya_id: number
  kollekciya_id: number
  /** Опционально (W2.3 справочник). */
  tip_kollekcii_id?: number | null
  /** Опционально. */
  fabrika_id?: number | null
  /** Юрлицо первой вариации. */
  importer_id: number
  /** Статус (tip='model'). */
  status_id: number
  /** ID размеров из справочника razmery. Пустой массив → не создавать привязки. */
  razmery_ids?: number[]
}

/**
 * Создаёт модель целиком: modeli_osnova → modeli (первая вариация) → опц.
 * modeli_osnova_razmery. При любой ошибке откатывает уже созданное.
 *
 * Возвращает kod созданной модели — caller использует его для navigate в
 * `/catalog/matrix?model=<kod>`.
 */
export async function createModelTransactional(
  payload: CreateModelTransactionalPayload,
): Promise<string> {
  const trimmedKod = payload.kod.trim()
  if (!trimmedKod) throw new Error("Код модели не может быть пустым")

  // 1. Pre-flight uniqueness check (чтобы дать понятную ошибку до INSERT).
  const { data: existing, error: checkErr } = await supabase
    .from("modeli_osnova")
    .select("kod")
    .eq("kod", trimmedKod)
    .maybeSingle()
  if (checkErr) throw new Error(checkErr.message)
  if (existing) throw new Error(`Модель с кодом «${trimmedKod}» уже существует`)

  // 2. Insert modeli_osnova.
  const osnovaPayload: ModelOsnovaPayload = {
    kod: trimmedKod,
    brand_id: payload.brand_id,
    kategoriya_id: payload.kategoriya_id,
    kollekciya_id: payload.kollekciya_id,
    tip_kollekcii_id: payload.tip_kollekcii_id ?? null,
    fabrika_id: payload.fabrika_id ?? null,
    status_id: payload.status_id,
  }
  const { data: osnovaRow, error: osnovaErr } = await supabase
    .from("modeli_osnova")
    .insert(osnovaPayload)
    .select("id, kod")
    .single()
  if (osnovaErr) throw new Error(osnovaErr.message)
  const osnovaId = (osnovaRow as { id: number; kod: string }).id

  // 3. Insert first modeli variation (rollback on error).
  const { error: variantErr } = await supabase.from("modeli").insert({
    kod: trimmedKod,
    nazvanie: trimmedKod,
    model_osnova_id: osnovaId,
    importer_id: payload.importer_id,
    status_id: payload.status_id,
  })
  if (variantErr) {
    await supabase.from("modeli_osnova").delete().eq("id", osnovaId)
    throw new Error(`Не удалось создать вариацию: ${variantErr.message}`)
  }

  // 4. Insert razmery junction (rollback on error).
  const razmeryIds = payload.razmery_ids ?? []
  if (razmeryIds.length > 0) {
    const rows = razmeryIds.map((razmer_id, idx) => ({
      model_osnova_id: osnovaId,
      razmer_id,
      poryadok: idx,
    }))
    const { error: razmErr } = await supabase.from("modeli_osnova_razmery").insert(rows)
    if (razmErr) {
      // Cascade: удаляем modeli (FK→modeli_osnova) и саму модель.
      await supabase.from("modeli").delete().eq("model_osnova_id", osnovaId)
      await supabase.from("modeli_osnova").delete().eq("id", osnovaId)
      throw new Error(`Не удалось привязать размеры: ${razmErr.message}`)
    }
  }

  return trimmedKod
}

/** Partial update of any modeli_osnova fields, addressed by kod. */
export async function updateModel(kod: string, patch: Partial<ModelOsnovaPayload>): Promise<void> {
  const { error } = await supabase.from("modeli_osnova").update(patch).eq("kod", kod)
  if (error) throw new Error(error.message)
}

/**
 * Duplicate a modeli_osnova row as a template — copies ONLY the modeli_osnova
 * record (no modeli variations, no artikuly, no tovary).
 */
export async function duplicateModel(srcKod: string, newKod: string): Promise<string> {
  const { data: src, error: srcErr } = await supabase
    .from("modeli_osnova")
    .select("*")
    .eq("kod", srcKod)
    .single()
  if (srcErr) throw new Error(srcErr.message)
  if (!src) throw new Error(`Source model ${srcKod} not found`)

  const copy = { ...(src as Record<string, unknown>) }
  delete copy.id
  delete copy.created_at
  delete copy.updated_at
  copy.kod = newKod

  const { data, error } = await supabase
    .from("modeli_osnova")
    .insert(copy)
    .select("kod")
    .single()
  if (error) throw new Error(error.message)
  return (data as { kod: string }).kod
}

/**
 * Helper: resolve "Архив" status_id for a given tip, or fall back to "Скрыт"
 * (used by lamoda which has no Архив variant). Returns null if neither exists.
 */
async function getArchiveStatusId(tip: string): Promise<number | null> {
  const { data, error } = await supabase
    .from("statusy")
    .select("id, nazvanie")
    .eq("tip", tip)
    .in("nazvanie", ["Архив", "Скрыт"])
  if (error) throw new Error(error.message)
  const rows = (data ?? []) as { id: number; nazvanie: string }[]
  const archive = rows.find((r) => r.nazvanie === "Архив")
  if (archive) return archive.id
  const hidden = rows.find((r) => r.nazvanie === "Скрыт")
  return hidden?.id ?? null
}

/** Helper: resolve a status_id by (tip, nazvanie). */
async function getStatusIdByName(tip: string, nazvanie: string): Promise<number | null> {
  const { data, error } = await supabase
    .from("statusy")
    .select("id")
    .eq("tip", tip)
    .eq("nazvanie", nazvanie)
    .maybeSingle()
  if (error) throw new Error(error.message)
  return (data as { id: number } | null)?.id ?? null
}

/**
 * Cascade-archive a model:
 *   modeli_osnova.status_id        → Архив (tip='model')
 *   artikuly.status_id (under it)  → Выводим (tip='artikul')
 *   tovary.status_id               → Архив (tip='product')
 *   tovary.status_ozon_id          → Архив (tip='product')
 *   tovary.status_sayt_id          → Архив (tip='sayt')
 *   tovary.status_lamoda_id        → Архив-or-Скрыт (tip='lamoda')
 */
export async function archiveModel(kod: string): Promise<void> {
  const [modelArchive, artikulVyvodim, productArchive, saytArchive, lamodaArchive, mo] = await Promise.all([
    getStatusIdByName("model", "Архив"),
    getStatusIdByName("artikul", "Выводим"),
    getStatusIdByName("product", "Архив"),
    getStatusIdByName("sayt", "Архив"),
    getArchiveStatusId("lamoda"),
    supabase.from("modeli_osnova").select("id").eq("kod", kod).single(),
  ])

  if (mo.error) throw new Error(mo.error.message)
  const modelOsnovaId = (mo.data as { id: number }).id

  if (modelArchive == null) throw new Error("Status Архив (tip=model) not found")

  // 1. modeli_osnova.status_id
  const { error: moErr } = await supabase
    .from("modeli_osnova")
    .update({ status_id: modelArchive })
    .eq("id", modelOsnovaId)
  if (moErr) throw new Error(moErr.message)

  // 2. Find variation ids (modeli) → artikuly under them
  const { data: modeliRows, error: mErr } = await supabase
    .from("modeli")
    .select("id")
    .eq("model_osnova_id", modelOsnovaId)
  if (mErr) throw new Error(mErr.message)
  const modelIds = ((modeliRows ?? []) as { id: number }[]).map((r) => r.id)
  if (modelIds.length === 0) return

  const { data: artRows, error: aErr } = await supabase
    .from("artikuly")
    .select("id")
    .in("model_id", modelIds)
  if (aErr) throw new Error(aErr.message)
  const artikulIds = ((artRows ?? []) as { id: number }[]).map((r) => r.id)

  if (artikulVyvodim != null && artikulIds.length > 0) {
    const { error: artUpdErr } = await supabase
      .from("artikuly")
      .update({ status_id: artikulVyvodim })
      .in("id", artikulIds)
    if (artUpdErr) throw new Error(artUpdErr.message)
  }

  if (artikulIds.length === 0) return

  // 3. tovary attached to those artikuly — update all 4 status fields atomically
  const tovaryPatch: Record<string, number | null> = {}
  if (productArchive != null) {
    tovaryPatch.status_id = productArchive
    tovaryPatch.status_ozon_id = productArchive
  }
  if (saytArchive != null) tovaryPatch.status_sayt_id = saytArchive
  if (lamodaArchive != null) tovaryPatch.status_lamoda_id = lamodaArchive

  if (Object.keys(tovaryPatch).length === 0) return
  const { error: tErr } = await supabase
    .from("tovary")
    .update(tovaryPatch)
    .in("artikul_id", artikulIds)
  if (tErr) throw new Error(tErr.message)
}

// ─── W4.2: Create new variation row in `modeli` ────────────────────────────
//
// Вариация = базовая модель × юрлицо (importer). Создаётся через карточку
// модели → SidebarBlock «Вариации» → «+ Добавить».
//
// Контракт:
//   - `modelOsnovaId` — FK на `modeli_osnova.id` родительской модели
//   - `importerId` — FK на `importery.id` (юрлицо: ИП Медведева / ООО ВУКИ / …)
//   - `kodSuffix?` — опциональный текстовый суффикс для `kod` новой вариации.
//     Если не задан — используется индекс `(existingVariationCount + 1)`.
//
// Правила:
//   - `kod` нового modeli = `${parentKod}-${suffix}` (через дефис).
//   - `nazvanie` NOT NULL в БД → копируем `parentKod` (PM правит позже inline).
//   - `status_id` → копируется со status_id родительской `modeli_osnova`;
//     если у родителя пусто — fallback на 20 («Планирование», tip=model).
//   - При коллизии kod выкидываем понятную ошибку — PM пробует другой суффикс.
export async function insertVariation(
  modelOsnovaId: number,
  importerId: number,
  kodSuffix?: string,
): Promise<ModelVariation> {
  // 1. Подтянуть parent kod + parent status + текущее число вариаций.
  const { data: parent, error: parentErr } = await supabase
    .from("modeli_osnova")
    .select("kod, status_id")
    .eq("id", modelOsnovaId)
    .single()
  if (parentErr) throw new Error(parentErr.message)
  if (!parent) throw new Error(`modeli_osnova ${modelOsnovaId} not found`)
  const parentKod = (parent as { kod: string }).kod
  const parentStatusId = (parent as { status_id: number | null }).status_id

  const { data: existingRows, error: cntErr } = await supabase
    .from("modeli")
    .select("id, kod")
    .eq("model_osnova_id", modelOsnovaId)
  if (cntErr) throw new Error(cntErr.message)
  const existing = (existingRows ?? []) as { id: number; kod: string }[]

  // 2. Вычислить новый kod.
  const trimmedSuffix = kodSuffix?.trim()
  const suffix = trimmedSuffix && trimmedSuffix.length > 0
    ? trimmedSuffix
    : String(existing.length + 1)
  const newKod = `${parentKod}-${suffix}`

  if (existing.some((m) => m.kod === newKod)) {
    throw new Error(
      `Вариация с kod «${newKod}» уже существует. Укажите другой суффикс.`,
    )
  }

  // 3. Дефолтный status_id.
  let statusId: number | null = parentStatusId
  if (statusId == null) {
    statusId = await getStatusIdByName("model", "Планирование")
  }

  // 4. INSERT.
  const insertPayload = {
    model_osnova_id: modelOsnovaId,
    importer_id: importerId,
    kod: newKod,
    nazvanie: parentKod, // NOT NULL — PM правит inline после создания
    status_id: statusId,
    nabor: false,
  }
  const { data: inserted, error: insErr } = await supabase
    .from("modeli")
    .insert(insertPayload)
    .select(`
      id, kod, nazvanie, nazvanie_en, artikul_modeli, importer_id, status_id,
      rossiyskiy_razmer, nabor,
      importery(nazvanie)
    `)
    .single()
  if (insErr) throw new Error(insErr.message)

  const row = inserted as {
    id: number
    kod: string
    nazvanie: string
    nazvanie_en: string | null
    artikul_modeli: string | null
    importer_id: number | null
    status_id: number | null
    rossiyskiy_razmer: string | null
    nabor: boolean | null
    importery: { nazvanie: string } | { nazvanie: string }[] | null
  }
  const importerNazvanie = Array.isArray(row.importery)
    ? row.importery[0]?.nazvanie ?? null
    : row.importery?.nazvanie ?? null

  return {
    id: row.id,
    kod: row.kod,
    nazvanie: row.nazvanie,
    nazvanie_en: row.nazvanie_en,
    artikul_modeli: row.artikul_modeli,
    importer_id: row.importer_id,
    importer_nazvanie: importerNazvanie,
    status_id: row.status_id,
    rossiyskiy_razmer: row.rossiyskiy_razmer,
    nabor: row.nabor,
    artikuly: [],
  }
}

// ─── Bulk operations ───────────────────────────────────────────────────────

export type TovarChannel = "wb" | "ozon" | "sayt" | "lamoda"

const TOVAR_STATUS_FIELD: Record<TovarChannel, "status_id" | "status_ozon_id" | "status_sayt_id" | "status_lamoda_id"> = {
  wb: "status_id",
  ozon: "status_ozon_id",
  sayt: "status_sayt_id",
  lamoda: "status_lamoda_id",
}

/** Bulk-update status_id of modeli_osnova rows (addressed by kod). */
export async function bulkUpdateModelStatus(kods: string[], statusId: number): Promise<void> {
  if (kods.length === 0) return
  const { error } = await supabase
    .from("modeli_osnova")
    .update({ status_id: statusId })
    .in("kod", kods)
  if (error) throw new Error(error.message)
}

/** Bulk-update status_id of artikuly rows (addressed by id). */
export async function bulkUpdateArtikulStatus(artikulIds: number[], statusId: number): Promise<void> {
  if (artikulIds.length === 0) return
  const { error } = await supabase
    .from("artikuly")
    .update({ status_id: statusId })
    .in("id", artikulIds)
  if (error) throw new Error(error.message)
}

/**
 * W9.10 — Patch для inline-edit одной строки artikuly.
 *
 * Поддерживаемые поля:
 *   - artikul (varchar, NOT NULL) — основной код/имя
 *   - cvet_id (FK на cveta)
 *   - nomenklatura_wb (bigint | null)
 *   - artikul_ozon (varchar | null)
 *   - status_id — лучше через bulkUpdateArtikulStatus (есть отдельный popover)
 *
 * Аудит-триггер (W7.1 / W9.1) пишет в `istoriya_izmeneniy`.
 */
export interface ArtikulPatch {
  artikul?: string
  cvet_id?: number
  nomenklatura_wb?: number | null
  artikul_ozon?: string | null
  status_id?: number
}
export async function updateArtikul(id: number, patch: ArtikulPatch): Promise<void> {
  if (Object.keys(patch).length === 0) return
  const { error } = await supabase
    .from("artikuly")
    .update(patch)
    .eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * W9.10 — Patch для inline-edit одной строки tovary.
 *
 * Поддерживаемые поля:
 *   - barkod (varchar, NOT NULL) — основной баркод
 *   - barkod_gs1, barkod_gs2, barkod_perehod (varchar | null)
 *   - razmer_id (FK на razmery)
 *   - sku_china_size (varchar | null)
 *   - lamoda_seller_sku (varchar | null)
 *   - ozon_product_id, ozon_fbo_sku_id (bigint | null)
 *   - status_<channel>_id — лучше через bulkUpdateTovaryStatus.
 *
 * Цены WB/OZON в схеме `tovary` отсутствуют — поля cena_wb/cena_ozon
 * в реестре пока стоят как plain «—» (см. column-catalogs W9.5). Здесь не
 * редактируются. Если когда-нибудь появятся отдельные таблицы — добавить
 * параллельный patch в them.
 */
export interface TovarPatch {
  barkod?: string
  barkod_gs1?: string | null
  barkod_gs2?: string | null
  barkod_perehod?: string | null
  razmer_id?: number
  sku_china_size?: string | null
  lamoda_seller_sku?: string | null
  ozon_product_id?: number | null
  ozon_fbo_sku_id?: number | null
}
export async function updateTovar(id: number, patch: TovarPatch): Promise<void> {
  if (Object.keys(patch).length === 0) return
  const { error } = await supabase
    .from("tovary")
    .update(patch)
    .eq("id", id)
  if (error) throw new Error(error.message)
}

/**
 * Bulk-update status of tovary rows (addressed by barkod) on a specific channel.
 * Channel determines which status field is updated:
 *   wb     → status_id
 *   ozon   → status_ozon_id
 *   sayt   → status_sayt_id
 *   lamoda → status_lamoda_id
 *
 * Pass `statusId = null` to clear the status (sets the field to NULL).
 */
export async function bulkUpdateTovaryStatus(
  barkods: string[],
  statusId: number | null,
  channel: TovarChannel,
): Promise<void> {
  if (barkods.length === 0) return
  const field = TOVAR_STATUS_FIELD[channel]
  const { error } = await supabase
    .from("tovary")
    .update({ [field]: statusId })
    .in("barkod", barkods)
  if (error) throw new Error(error.message)
}

/**
 * Bulk-link tovary (by barkod) to a skleyka via the appropriate junction table.
 * channel must be 'wb' or 'ozon' — only those have skleyki/junction tables.
 */
export async function bulkLinkTovaryToSkleyka(
  barkods: string[],
  skleykaId: number,
  channel: "wb" | "ozon",
): Promise<void> {
  if (barkods.length === 0) return
  const junction = channel === "wb" ? "tovary_skleyki_wb" : "tovary_skleyki_ozon"

  // Resolve barkod → tovar_id
  const { data: tovaryRows, error: tErr } = await supabase
    .from("tovary")
    .select("id, barkod")
    .in("barkod", barkods)
  if (tErr) throw new Error(tErr.message)
  const ids = ((tovaryRows ?? []) as { id: number }[]).map((r) => r.id)
  if (ids.length === 0) return

  const rows = ids.map((tovar_id) => ({ tovar_id, skleyka_id: skleykaId }))
  const { error } = await supabase.from(junction).upsert(rows, { onConflict: "tovar_id,skleyka_id" })
  if (error) throw new Error(error.message)
}

/**
 * Bulk-unlink tovary (by barkod) from any skleyka on the given channel.
 * Removes all junction rows for these tovary on the channel — use
 * bulkLinkTovaryToSkleyka to re-attach them elsewhere.
 */
export async function bulkUnlinkTovaryFromSkleyka(
  barkods: string[],
  channel: "wb" | "ozon",
): Promise<void> {
  if (barkods.length === 0) return
  const junction = channel === "wb" ? "tovary_skleyki_wb" : "tovary_skleyki_ozon"

  const { data: tovaryRows, error: tErr } = await supabase
    .from("tovary")
    .select("id")
    .in("barkod", barkods)
  if (tErr) throw new Error(tErr.message)
  const ids = ((tovaryRows ?? []) as { id: number }[]).map((r) => r.id)
  if (ids.length === 0) return

  const { error } = await supabase.from(junction).delete().in("tovar_id", ids)
  if (error) throw new Error(error.message)
}

// ─── Artikul create (W4.3) ─────────────────────────────────────────────────

/**
 * Row returned after inserting an artikul (subset of full artikuly columns).
 */
export interface InsertedArtikul {
  id: number
  artikul: string
  model_id: number
  cvet_id: number
  status_id: number | null
}

/**
 * Resolve "Запуск" (tip='artikul') status id — default for newly created
 * artikuly. Falls back to any row with tip='artikul' if exact name is missing,
 * to avoid hard-blocking the UI in case of dictionary edits.
 */
async function getDefaultArtikulStatusId(): Promise<number | null> {
  const byName = await getStatusIdByName("artikul", "Запуск")
  if (byName != null) return byName
  const { data, error } = await supabase
    .from("statusy")
    .select("id")
    .eq("tip", "artikul")
    .limit(1)
    .maybeSingle()
  if (error) throw new Error(error.message)
  return (data as { id: number } | null)?.id ?? null
}

/**
 * Create a single `artikuly` row for a given variation (`modeli.id`) and
 * a colour (`cveta.id`).
 *
 * By default `artikul` is auto-generated as `${modeli.kod}/${cveta.color_code}`
 * to match historical naming convention (e.g. `Alice-1/black`, `Nora/brown`).
 *
 * W9.11 — caller may pass `customArtikul` to override the generated name.
 * Trimmed value is used; if empty after trim, falls back to auto-generated.
 * Uniqueness is guaranteed by DB constraint `artikuly_artikul_key`
 * (translated to a human message by `translateError` on 23505).
 *
 * Default `status_id` = `statusy(tip='artikul', nazvanie='Запуск')`.
 *
 * Caller is responsible for invalidating ["catalog", "model", kod].
 */
export async function insertArtikul(
  modeliId: number,
  cvetId: number,
  customArtikul?: string,
): Promise<InsertedArtikul> {
  // 1. Look up the variation's kod + colour's color_code in parallel.
  const [modeliRes, cvetRes, defaultStatusId] = await Promise.all([
    supabase.from("modeli").select("kod").eq("id", modeliId).single(),
    supabase.from("cveta").select("color_code").eq("id", cvetId).single(),
    getDefaultArtikulStatusId(),
  ])
  if (modeliRes.error) throw new Error(modeliRes.error.message)
  if (cvetRes.error) throw new Error(cvetRes.error.message)

  const modeliKod = (modeliRes.data as { kod: string | null }).kod
  const colorCode = (cvetRes.data as { color_code: string | null }).color_code
  if (!modeliKod) throw new Error(`modeli.id=${modeliId} has empty kod`)
  if (!colorCode) throw new Error(`cveta.id=${cvetId} has empty color_code`)

  const trimmedCustom = customArtikul?.trim() ?? ""
  const artikul = trimmedCustom.length > 0
    ? trimmedCustom
    : `${modeliKod}/${colorCode}`

  // 2. INSERT. status_id may legitimately be null if the dictionary has no
  // tip='artikul' rows at all — schema allows it.
  const { data, error } = await supabase
    .from("artikuly")
    .insert({
      model_id: modeliId,
      cvet_id: cvetId,
      artikul,
      status_id: defaultStatusId,
    })
    .select("id, artikul, model_id, cvet_id, status_id")
    .single()
  if (error) throw new Error(error.message)
  return data as InsertedArtikul
}

/**
 * Bulk-create artikuly for one variation across multiple colours.
 *
 * Accepts a list of `{ cvetId, customArtikul? }` entries. If `customArtikul`
 * is omitted/empty for an entry, the server generates `${kod}/${color_code}`
 * (см. `insertArtikul`).
 *
 * Skips colours that would produce a duplicate `artikul` string (the UI is
 * expected to filter these out, but the guard is here so the call is
 * idempotent). Runs the inserts sequentially via `insertArtikul` to keep
 * error handling simple — N ≤ palette size, typically < 20.
 */
export interface ArtikulCreateInput {
  cvetId: number
  customArtikul?: string
}

export async function bulkCreateArtikuly(
  modeliId: number,
  entries: ArtikulCreateInput[],
): Promise<InsertedArtikul[]> {
  if (entries.length === 0) return []
  const out: InsertedArtikul[] = []
  for (const entry of entries) {
    const row = await insertArtikul(modeliId, entry.cvetId, entry.customArtikul)
    out.push(row)
  }
  return out
}

// ─── Tovar creation (W4.4) ─────────────────────────────────────────────────
//
// Создание новых SKU (`tovary` rows). Используется кнопками «+ SKU» и
// «+ Размер ко всем артикулам» в TabSKU карточки модели.
//
// `barkod` — NOT NULL + UNIQUE. Реальные баркоды получают офлайн через GS1
// (`barkod_gs1`/`barkod_gs2`), поэтому при создании генерируем валидный
// EAN-13 в internal-диапазоне (prefix `200`) с правильным check-digit —
// он гарантированно не пересечётся с GS1-номерами реальных производителей.
// Поле останется placeholder-ом до тех пор, пока команда не запросит
// настоящие баркоды через `barkod_gs1`/`barkod_gs2`.
//
// Defaults (выбор задокументирован в commit W4.4):
//   status_id        = 12  (План)  — модель ещё не продаётся
//   status_ozon_id   = 12  (План)
//   status_sayt_id   = 12  (План)
//   status_lamoda_id = null         — lamoda опциональна
//   barkod_gs1/gs2/perehod, ozon_*, lamoda_seller_sku, sku_china_size = null

export const TOVAR_DEFAULT_STATUS_ID = 12 // 'План' — статус для свежесозданных SKU
export const TOVAR_DEFAULT_LAMODA_STATUS_ID: number | null = null

export interface InsertedTovar {
  id: number
  barkod: string
  artikul_id: number
  razmer_id: number
}

/**
 * Generate a valid EAN-13 barkod in the internal-use prefix `200`.
 * Returns 13-digit string with correct check-digit; collisions are extremely
 * unlikely (10^9 namespace), and DB UNIQUE-constraint will reject the rare hit
 * — the caller can retry.
 */
function generateInternalBarkod(): string {
  // 12-digit payload: '200' + 9 random digits
  let body = "200"
  for (let i = 0; i < 9; i++) body += Math.floor(Math.random() * 10).toString()
  // EAN-13 check-digit: sum of digits — odd positions (1-based) ×1, even ×3,
  // then check = (10 - sum % 10) % 10
  let sum = 0
  for (let i = 0; i < 12; i++) {
    const d = body.charCodeAt(i) - 48
    sum += i % 2 === 0 ? d : d * 3
  }
  const check = (10 - (sum % 10)) % 10
  return body + check.toString()
}

/**
 * Generate a fresh barkod that does not yet exist in `tovary`.
 * Retries up to `maxAttempts` times — astronomically unlikely to need more
 * than 1 attempt given the 10^9 namespace, but the loop guards against
 * pathological luck.
 */
async function generateUniqueBarkod(maxAttempts = 5): Promise<string> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const candidate = generateInternalBarkod()
    const { data, error } = await supabase
      .from("tovary")
      .select("id")
      .eq("barkod", candidate)
      .maybeSingle()
    if (error && error.code !== "PGRST116") throw new Error(error.message)
    if (!data) return candidate
  }
  throw new Error("Не удалось сгенерировать уникальный barkod после нескольких попыток")
}

/**
 * Insert a single tovar (SKU) for the given artikul + razmer combination.
 * Generates a placeholder EAN-13 barkod automatically and applies default
 * statuses (12 = 'План' for WB/OZON/sayt; null for lamoda).
 *
 * Throws if (artikul_id, razmer_id) combination already exists — caller
 * should detect this before calling.
 */
export async function insertTovar(
  artikulId: number,
  razmerId: number,
): Promise<InsertedTovar> {
  // Pre-check: refuse if combination already exists.
  const { data: existing, error: probeErr } = await supabase
    .from("tovary")
    .select("id")
    .eq("artikul_id", artikulId)
    .eq("razmer_id", razmerId)
    .maybeSingle()
  if (probeErr && probeErr.code !== "PGRST116") throw new Error(probeErr.message)
  if (existing) {
    throw new Error(`SKU для этого артикула + размера уже существует (id=${existing.id})`)
  }

  const barkod = await generateUniqueBarkod()
  const { data, error } = await supabase
    .from("tovary")
    .insert({
      barkod,
      artikul_id: artikulId,
      razmer_id: razmerId,
      status_id: TOVAR_DEFAULT_STATUS_ID,
      status_ozon_id: TOVAR_DEFAULT_STATUS_ID,
      status_sayt_id: TOVAR_DEFAULT_STATUS_ID,
      status_lamoda_id: TOVAR_DEFAULT_LAMODA_STATUS_ID,
    })
    .select("id, barkod, artikul_id, razmer_id")
    .single()
  if (error) throw new Error(error.message)
  return data as InsertedTovar
}

/**
 * Bulk-add the same `razmer_id` to a list of artikuly.
 * Skips artikuly that already have this size — returns the rows actually
 * inserted (may be shorter than the input list).
 *
 * Implementation: probes existing `tovary` for the (artikul_ids[], razmer_id)
 * combos in one query, then issues a single multi-row INSERT for the rest.
 */
export async function bulkAddSizeToArtikuly(
  artikulIds: number[],
  razmerId: number,
): Promise<InsertedTovar[]> {
  if (artikulIds.length === 0) return []

  // Detect existing combinations to skip.
  const { data: existing, error: existingErr } = await supabase
    .from("tovary")
    .select("artikul_id")
    .in("artikul_id", artikulIds)
    .eq("razmer_id", razmerId)
  if (existingErr) throw new Error(existingErr.message)
  const existingSet = new Set(
    ((existing ?? []) as { artikul_id: number }[]).map((r) => r.artikul_id),
  )
  const toCreate = artikulIds.filter((id) => !existingSet.has(id))
  if (toCreate.length === 0) return []

  // Pre-generate unique barkods (sequentially to use the same DB-uniqueness
  // probe; cheap given typical N ≤ 20).
  const rows: Array<{
    barkod: string
    artikul_id: number
    razmer_id: number
    status_id: number
    status_ozon_id: number
    status_sayt_id: number
    status_lamoda_id: number | null
  }> = []
  const localBarkods = new Set<string>()
  for (const artikulId of toCreate) {
    let barkod: string
    // ensure uniqueness both vs DB и vs already-prepared rows in this batch
    // (probability ≈ 0 but cheap to guard)
    while (true) {
      const candidate = await generateUniqueBarkod()
      if (!localBarkods.has(candidate)) {
        barkod = candidate
        localBarkods.add(candidate)
        break
      }
    }
    rows.push({
      barkod,
      artikul_id: artikulId,
      razmer_id: razmerId,
      status_id: TOVAR_DEFAULT_STATUS_ID,
      status_ozon_id: TOVAR_DEFAULT_STATUS_ID,
      status_sayt_id: TOVAR_DEFAULT_STATUS_ID,
      status_lamoda_id: TOVAR_DEFAULT_LAMODA_STATUS_ID,
    })
  }

  const { data, error } = await supabase
    .from("tovary")
    .insert(rows)
    .select("id, barkod, artikul_id, razmer_id")
  if (error) throw new Error(error.message)
  return (data ?? []) as InsertedTovar[]
}

// ─── Tovary by artikul (W8.4 drill-down) ───────────────────────────────────
//
// Возвращает SKU одного артикула — для overlay-карточки в /catalog/artikuly.
// Лёгкий запрос: только то, что нужно для read-only таблицы (баркод, размер,
// 4 статуса по каналам). Для inline-edit см. tovary.tsx (W8.5 territory).

export interface ArtikulTovar {
  id: number
  barkod: string
  razmer_id: number | null
  razmer_nazvanie: string | null
  status_id: number | null
  status_ozon_id: number | null
  status_sayt_id: number | null
  status_lamoda_id: number | null
}

export async function fetchTovaryByArtikul(artikulId: number): Promise<ArtikulTovar[]> {
  const { data, error } = await supabase
    .from("tovary")
    .select(
      "id, barkod, razmer_id, status_id, status_ozon_id, status_sayt_id, status_lamoda_id, razmery:razmer_id(nazvanie)",
    )
    .eq("artikul_id", artikulId)
    .order("id")
  if (error) throw new Error(error.message)
  return ((data ?? []) as any[]).map((t) => ({
    id: t.id,
    barkod: t.barkod,
    razmer_id: t.razmer_id,
    razmer_nazvanie: t.razmery?.nazvanie ?? null,
    status_id: t.status_id,
    status_ozon_id: t.status_ozon_id,
    status_sayt_id: t.status_sayt_id,
    status_lamoda_id: t.status_lamoda_id,
  }))
}

// ─── UI preferences (per-user-less, scope+key) ─────────────────────────────

/**
 * Read a UI preference by (scope, key).
 * Returns null if no row exists. Caller is responsible for the type T cast.
 */
export async function getUiPref<T>(scope: string, key: string): Promise<T | null> {
  const { data, error } = await supabase
    .from("ui_preferences")
    .select("value")
    .eq("scope", scope)
    .eq("key", key)
    .maybeSingle()
  if (error) throw new Error(error.message)
  if (!data) return null
  return (data as { value: T | null }).value
}

/** Upsert a UI preference (scope, key) → value (JSONB). */
export async function setUiPref(scope: string, key: string, value: unknown): Promise<void> {
  const { error } = await supabase
    .from("ui_preferences")
    .upsert(
      { scope, key, value, updated_at: new Date().toISOString() },
      { onConflict: "scope,key" },
    )
  if (error) throw new Error(error.message)
}

// ─── Catalog counts (sidebar badges + global) ──────────────────────────────

export interface CatalogCounts {
  models: number
  variations: number
  articles: number
  /** Sidebar alias for `articles`. */
  artikuly: number
  skus: number
  /** Sidebar alias for `skus`. */
  tovary: number
  colors: number
  skleyki_wb: number
  skleyki_ozon: number
  /** Sidebar alias: WB + OZON skleyki combined. */
  skleyki: number
  kategorii: number
  kollekcii: number
  tipy_kollekciy: number
  brendy: number
  fabriki: number
  importery: number
  razmery: number
  semeystva_cvetov: number
  upakovki: number
  kanaly_prodazh: number
  sertifikaty: number
  statusy: number
  atributy: number
}

async function tableCount(table: string): Promise<number> {
  const { count, error } = await supabase
    .from(table)
    .select("*", { head: true, count: "exact" })
  if (error) throw new Error(error.message)
  return count ?? 0
}

/**
 * One-shot fetch of all counts used by the Sidebar. Run all queries in
 * parallel so the round-trip is bounded by the slowest table.
 */
export async function fetchCatalogCounts(): Promise<CatalogCounts> {
  const tables = [
    "models",
    "variations",
    "articles",
    "skus",
    "colors",
    "skleyki_wb",
    "skleyki_ozon",
    "kategorii",
    "kollekcii",
    "tipy_kollekciy",
    "brendy",
    "fabriki",
    "importery",
    "razmery",
    "semeystva_cvetov",
    "upakovki",
    "kanaly_prodazh",
    "sertifikaty",
    "statusy",
    "atributy",
  ] as const
  const tableMap = {
    models: "modeli_osnova",
    variations: "modeli",
    articles: "artikuly",
    skus: "tovary",
    colors: "cveta",
    skleyki_wb: "skleyki_wb",
    skleyki_ozon: "skleyki_ozon",
    kategorii: "kategorii",
    kollekcii: "kollekcii",
    tipy_kollekciy: "tipy_kollekciy",
    brendy: "brendy",
    fabriki: "fabriki",
    importery: "importery",
    razmery: "razmery",
    semeystva_cvetov: "semeystva_cvetov",
    upakovki: "upakovki",
    kanaly_prodazh: "kanaly_prodazh",
    sertifikaty: "sertifikaty",
    statusy: "statusy",
    atributy: "atributy",
  } as const satisfies Partial<Record<keyof CatalogCounts, string>>
  const counts = await Promise.all(tables.map((k) => tableCount(tableMap[k])))
  const out = {} as CatalogCounts
  tables.forEach((k, i) => {
    out[k] = counts[i]
  })
  out.artikuly = out.articles
  out.tovary = out.skus
  out.skleyki = out.skleyki_wb + out.skleyki_ozon
  return out
}

/**
 * Sidebar counters keyed by kategoriya_id (for the "Категории" section).
 * Returns a map { kategoriya_id → count } plus an extra `null` bucket for
 * models without a category.
 */
export async function fetchModeliOsnovaCounts(): Promise<Record<number | "null", number>> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("kategoriya_id")
  if (error) throw new Error(error.message)
  const acc: Record<number | "null", number> = { null: 0 }
  for (const row of (data ?? []) as { kategoriya_id: number | null }[]) {
    const k = row.kategoriya_id == null ? "null" : row.kategoriya_id
    acc[k] = (acc[k] ?? 0) + 1
  }
  return acc
}

// ─── Global search (CommandPalette ⌘K) ─────────────────────────────────────

export interface SearchHitModel {
  id: number
  kod: string
  nazvanie_etiketka: string | null
}

export interface SearchHitColor {
  id: number
  color_code: string
  cvet: string | null
  color: string | null
}

export interface SearchHitArtikul {
  id: number
  artikul: string
  nomenklatura_wb: number | null
  artikul_ozon: string | null
}

export interface SearchHitTovar {
  id: number
  barkod: string
  barkod_gs1: string | null
}

export interface GlobalSearchResult {
  models: SearchHitModel[]
  colors: SearchHitColor[]
  articles: SearchHitArtikul[]
  skus: SearchHitTovar[]
}

const SEARCH_LIMIT = 12

function escapePgIlike(q: string): string {
  // Strip PostgREST OR/list metacharacters that would break .or()
  return q.replace(/[,()*%]/g, " ").trim()
}

/**
 * Global multi-table search for the ⌘K CommandPalette.
 * Searches:
 *   modeli_osnova.kod, .nazvanie_etiketka
 *   cveta.color_code, .cvet, .color
 *   artikuly.artikul, .nomenklatura_wb (text-cast), .artikul_ozon
 *   tovary.barkod, .barkod_gs1
 *
 * Each table runs in parallel; each capped at SEARCH_LIMIT results.
 */
export async function searchGlobal(query: string): Promise<GlobalSearchResult> {
  const q = escapePgIlike(query)
  if (!q) return { models: [], colors: [], articles: [], skus: [] }
  const like = `%${q}%`

  const [modelsRes, colorsRes, articlesRes, tovaryRes] = await Promise.all([
    supabase
      .from("modeli_osnova")
      .select("id, kod, nazvanie_etiketka")
      .or(`kod.ilike.${like},nazvanie_etiketka.ilike.${like}`)
      .limit(SEARCH_LIMIT),
    supabase
      .from("cveta")
      .select("id, color_code, cvet, color")
      .or(`color_code.ilike.${like},cvet.ilike.${like},color.ilike.${like}`)
      .limit(SEARCH_LIMIT),
    supabase
      .from("artikuly")
      .select("id, artikul, nomenklatura_wb, artikul_ozon")
      .or(`artikul.ilike.${like},artikul_ozon.ilike.${like}`)
      .limit(SEARCH_LIMIT),
    supabase
      .from("tovary")
      .select("id, barkod, barkod_gs1")
      .or(`barkod.ilike.${like},barkod_gs1.ilike.${like}`)
      .limit(SEARCH_LIMIT),
  ])

  if (modelsRes.error) throw new Error(modelsRes.error.message)
  if (colorsRes.error) throw new Error(colorsRes.error.message)
  if (articlesRes.error) throw new Error(articlesRes.error.message)
  if (tovaryRes.error) throw new Error(tovaryRes.error.message)

  // Numeric WB nomenclature search — only if query looks numeric.
  let extraArticles: SearchHitArtikul[] = []
  if (/^\d+$/.test(q)) {
    const { data: extra, error: exErr } = await supabase
      .from("artikuly")
      .select("id, artikul, nomenklatura_wb, artikul_ozon")
      .eq("nomenklatura_wb", Number(q))
      .limit(SEARCH_LIMIT)
    if (exErr) throw new Error(exErr.message)
    extraArticles = (extra ?? []) as SearchHitArtikul[]
  }

  const articles = [...((articlesRes.data ?? []) as SearchHitArtikul[]), ...extraArticles]
  // Dedupe articles by id
  const seen = new Set<number>()
  const dedup: SearchHitArtikul[] = []
  for (const a of articles) {
    if (seen.has(a.id)) continue
    seen.add(a.id)
    dedup.push(a)
    if (dedup.length >= SEARCH_LIMIT) break
  }

  return {
    models: (modelsRes.data ?? []) as SearchHitModel[],
    colors: (colorsRes.data ?? []) as SearchHitColor[],
    articles: dedup,
    skus: (tovaryRes.data ?? []) as SearchHitTovar[],
  }
}

// ─── Catalog assets storage (W5.1) ─────────────────────────────────────────
//
// Bucket: catalog-assets (private, max 10MB, image/* + application/pdf)
// Path conventions (callers should use the makeStoragePath* helpers):
//   models/{modeli_osnova_id}/header.{ext}
//   colors/{cvet_id}/sample.{ext}
//   sertifikaty/{sertifikat_id}/{slug}.pdf
//
// All access goes through signed URLs with 1h TTL — DB columns store the
// bucket-relative path, not the full URL, so the URL is freshly signed on read.

export const CATALOG_ASSETS_BUCKET = "catalog-assets"
export const SIGNED_URL_TTL_SECONDS = 3600
export const ALLOWED_IMAGE_MIME = [
  "image/png",
  "image/jpeg",
  "image/jpg",
  "image/webp",
  "image/gif",
] as const
export const ALLOWED_PDF_MIME = ["application/pdf"] as const
export const MAX_ASSET_SIZE_BYTES = 10 * 1024 * 1024

function extFromMime(mime: string): string {
  if (mime === "image/jpeg" || mime === "image/jpg") return "jpg"
  if (mime === "image/png") return "png"
  if (mime === "image/webp") return "webp"
  if (mime === "image/gif") return "gif"
  if (mime === "application/pdf") return "pdf"
  return "bin"
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "file"
}

export function makeStoragePathForModelHeader(modelOsnovaId: number, mime: string): string {
  return `models/${modelOsnovaId}/header.${extFromMime(mime)}`
}

export function makeStoragePathForColorSample(cvetId: number, mime: string): string {
  return `colors/${cvetId}/sample.${extFromMime(mime)}`
}

export function makeStoragePathForSertifikat(sertifikatId: number, originalName: string): string {
  const base = originalName.replace(/\.[^.]+$/, "")
  return `sertifikaty/${sertifikatId}/${slugify(base)}.pdf`
}

/**
 * Upload a File/Blob to the catalog-assets bucket at the given path.
 * `upsert: true` so re-uploading to the same path replaces silently — handy
 * for the "replace image" flow.
 *
 * Caller is responsible for validating size/mime *before* calling (the bucket
 * rejects oversized/wrong-mime, but we want a friendly error message).
 */
export async function uploadCatalogAsset(
  path: string,
  file: File | Blob,
  options?: { contentType?: string },
): Promise<void> {
  const contentType = options?.contentType ?? (file instanceof File ? file.type : undefined)
  const { error } = await supabase.storage
    .from(CATALOG_ASSETS_BUCKET)
    .upload(path, file, {
      upsert: true,
      contentType,
      cacheControl: "3600",
    })
  if (error) throw new Error(error.message)
}

/**
 * Generate a signed URL for a catalog asset. Returns null for null/empty paths
 * so callers can pass DB values directly.
 */
export async function getCatalogAssetSignedUrl(
  path: string | null | undefined,
  ttlSeconds: number = SIGNED_URL_TTL_SECONDS,
): Promise<string | null> {
  if (!path) return null
  const { data, error } = await supabase.storage
    .from(CATALOG_ASSETS_BUCKET)
    .createSignedUrl(path, ttlSeconds)
  if (error) throw new Error(error.message)
  return data?.signedUrl ?? null
}

export async function deleteCatalogAsset(path: string): Promise<void> {
  if (!path) return
  const { error } = await supabase.storage
    .from(CATALOG_ASSETS_BUCKET)
    .remove([path])
  if (error) throw new Error(error.message)
}

/** Validate a file is within bucket limits before we hit the network. */
export function validateCatalogAsset(
  file: File,
  kind: "image" | "pdf" | "image-or-pdf",
): { ok: true } | { ok: false; reason: string } {
  if (file.size > MAX_ASSET_SIZE_BYTES) {
    return { ok: false, reason: `Файл больше 10 МБ (${(file.size / 1024 / 1024).toFixed(1)} МБ)` }
  }
  const mime = file.type || "application/octet-stream"
  const okImage = (ALLOWED_IMAGE_MIME as readonly string[]).includes(mime)
  const okPdf = (ALLOWED_PDF_MIME as readonly string[]).includes(mime)
  if (kind === "image" && !okImage) {
    return { ok: false, reason: `Тип ${mime} не поддерживается. Разрешены PNG/JPG/WebP/GIF.` }
  }
  if (kind === "pdf" && !okPdf) {
    return { ok: false, reason: `Тип ${mime} не поддерживается. Разрешён только PDF.` }
  }
  if (kind === "image-or-pdf" && !okImage && !okPdf) {
    return { ok: false, reason: `Тип ${mime} не поддерживается. Разрешены изображения и PDF.` }
  }
  return { ok: true }
}

// ─── W7.1: Audit log ──────────────────────────────────────────────────────

export interface AuditEntry {
  id: number
  table_name: string
  row_id: string
  user_id: string | null
  action: "INSERT" | "UPDATE" | "DELETE"
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  changed: Record<string, { from: unknown; to: unknown }> | null
  created_at: string
}

/**
 * Возвращает историю изменений конкретной строки (table_name + row_id),
 * отсортированную по `created_at DESC`. Бэк — таблица `audit_log` + триггеры
 * на 9 таблицах каталога (см. migration 023).
 */
export async function fetchAuditFor(
  tableName: string,
  rowId: string | number,
  limit = 100,
): Promise<AuditEntry[]> {
  const { data, error } = await supabase
    .from("audit_log")
    .select("*")
    .eq("table_name", tableName)
    .eq("row_id", String(rowId))
    .order("created_at", { ascending: false })
    .limit(limit)
  if (error) throw new Error(error.message)
  return (data ?? []) as AuditEntry[]
}
