// Domain types for the Wookiee catalog.
//
// These match the Supabase schema after Wave 0 (2026-05-07) catalog rework.
// Source of truth: `wookiee-hub/src/lib/supabase/database.types.ts` (autogen).
// This file exposes hand-curated, ergonomic interfaces over those generated
// types so the UI doesn't have to juggle 6-level Supabase generics.

// ─── Statuses ──────────────────────────────────────────────────────────────

/** All status `tip` values currently in the `statusy` table (Wave 0 expanded). */
export type StatusTip =
  | "model"
  | "artikul"
  | "product"
  | "sayt"
  | "color"
  | "lamoda"

export interface Status {
  id: number
  nazvanie: string
  tip: StatusTip
  /** Tailwind/ColorPalette key (`green`, `amber`, `red`, `blue`, `gray`). */
  color?: string | null
}

// ─── Field ownership level ────────────────────────────────────────────────

/**
 * Каждое поле каталога живёт на одном из 4 уровней иерархии:
 *  - model       → modeli_osnova
 *  - variation   → modeli
 *  - artikul     → artikuly
 *  - sku         → tovary
 */
export type FieldLevel = "model" | "variation" | "artikul" | "sku"

// ─── Reference types ──────────────────────────────────────────────────────

export interface Kategoriya {
  id: number
  nazvanie: string
  opisanie?: string | null
}

export interface Kollekciya {
  id: number
  nazvanie: string
  opisanie?: string | null
  god_zapuska?: number | null
}

export interface Fabrika {
  id: number
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

export interface Importer {
  id: number
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

export interface Razmer {
  id: number
  /** `nazvanie` в БД NOT NULL — основной ключ для UI (XS/S/M/...). */
  nazvanie: string
  poryadok: number
  ru?: string | null
  eu?: string | null
  china?: string | null
}

// ─── New tables (Wave 0) ──────────────────────────────────────────────────

export interface SemeystvoCveta {
  id: number
  kod: string
  nazvanie: string
  opisanie?: string | null
  poryadok?: number | null
}

export interface Upakovka {
  id: number
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

export interface KanalProdazh {
  id: number
  kod: string
  nazvanie: string
  short?: string | null
  color?: string | null
  active?: boolean | null
  poryadok?: number | null
}

export interface UiPreference {
  id: number
  scope: string
  key: string
  value: unknown
  updated_at?: string | null
}

// ─── Cveta ────────────────────────────────────────────────────────────────
//
// ⚠ В реальной БД название колонок:
//   - `cvet`  — RU название цвета
//   - `color` — EN/латиницей
//   `lastovica` — varchar (значения "белая"/"чёрная"/null), не boolean.
//   `semeystvo` — текстовый код (legacy), `semeystvo_id` — FK на `semeystva_cvetov`.

export interface Cvet {
  id: number
  color_code: string
  cvet?: string | null
  color?: string | null
  lastovica?: string | null
  semeystvo?: string | null
  semeystvo_id?: number | null
  status_id?: number | null
  hex?: string | null
  created_at?: string | null
  updated_at?: string | null
}

// ─── Modeli osnova / modeli / artikuly / tovary ──────────────────────────

export interface ModelOsnova {
  id: number
  kod: string
  /** FK to `brendy.id`. NOT NULL in DB — каждая модель обязательно принадлежит бренду (WOOKIEE / TELOWAY). */
  brand_id: number
  kategoriya_id?: number | null
  kollekciya_id?: number | null
  fabrika_id?: number | null
  status_id?: number | null

  // Состав / производство
  tip_kollekcii?: string | null
  /** W2.3: FK to `tipy_kollekciy.id`. Authoritative source going forward; `tip_kollekcii` (text) kept temporarily for back-compat. */
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

  // Контент
  nazvanie_etiketka?: string | null
  nazvanie_sayt?: string | null
  opisanie_sayt?: string | null
  details?: string | null
  description?: string | null
  tegi?: string | null
  notion_link?: string | null
  notion_strategy_link?: string | null
  yandex_disk_link?: string | null
  /** W5.2: storage path inside catalog-assets bucket (e.g. models/123/header.jpg). Resolve via getCatalogAssetSignedUrl(). */
  header_image_url?: string | null

  // Атрибуты по категории
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

  // Сертификация
  tnved?: string | null
  gruppa_sertifikata?: string | null

  created_at?: string | null
  updated_at?: string | null
}

export interface Model {
  id: number
  kod: string
  nazvanie: string
  nazvanie_en?: string | null
  artikul_modeli?: string | null
  model_osnova_id?: number | null
  importer_id?: number | null
  status_id?: number | null
  nabor?: boolean | null
  rossiyskiy_razmer?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface Artikul {
  id: number
  artikul: string
  model_id?: number | null
  cvet_id?: number | null
  status_id?: number | null
  nomenklatura_wb?: number | null
  artikul_ozon?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface Tovar {
  id: number
  barkod: string
  barkod_gs1?: string | null
  barkod_gs2?: string | null
  barkod_perehod?: string | null
  artikul_id?: number | null
  razmer_id?: number | null
  status_id?: number | null
  status_ozon_id?: number | null
  status_sayt_id?: number | null
  status_lamoda_id?: number | null
  ozon_product_id?: number | null
  ozon_fbo_sku_id?: number | null
  lamoda_seller_sku?: string | null
  sku_china_size?: string | null
  created_at?: string | null
  updated_at?: string | null
}

// ─── Sklejki ──────────────────────────────────────────────────────────────
// Текущая БД использует две отдельные таблицы (skleyki_wb, skleyki_ozon)
// + junction-таблицы. Когда Wave 2 объединит их в `sklejki` (channel),
// тип ниже останется применим — добавим `channel` поле.

export interface SkleykaWb {
  id: number
  nazvanie: string
  importer_id?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export interface SkleykaOzon {
  id: number
  nazvanie: string
  importer_id?: number | null
  created_at?: string | null
  updated_at?: string | null
}

// ─── Sertifikaty ──────────────────────────────────────────────────────────

export interface Sertifikat {
  id: number
  nazvanie: string
  tip?: string | null
  nomer?: string | null
  /** ISO date (yyyy-mm-dd). */
  data_vydachi?: string | null
  /** ISO date (yyyy-mm-dd). */
  data_okonchaniya?: string | null
  organ_sertifikacii?: string | null
  file_url?: string | null
  gruppa_sertifikata?: string | null
  created_at?: string | null
  updated_at?: string | null
}

// ─── ATTRIBUTES_BY_CATEGORY + FIELD_LEVEL ─────────────────────────────────
//
// Скопировано из эталонного MVP (`redesign + PIX/wookiee_matrix_mvp_v4.jsx`)
// и расширено под актуальные ID `kategorii` в БД (Wave 0):
//   1 Комплект белья │ 2 Трусы │ 3 Боди женское │ 4 Леггинсы │ 5 Лонгслив
//   6 Рашгард       │ 7 Топ   │ 8 Футболка     │ 10 Велосипедки │ 11 Бюстгалтер
//
// Привязка ID-категорий ↔ массив атрибутов сохраняется. Wave 2 уточнит
// списки опций для категорий, не покрытых MVP (леггинсы, лонгслив, рашгард,
// футболка, велосипедки) — пока используем минимальный «общий» набор.

export type AttributeFieldType =
  | "text"
  | "number"
  | "select"
  | "multiselect"
  | "textarea"

export interface AttributeFieldDef {
  /** Колонка в `modeli_osnova`. */
  key: string
  label: string
  type: AttributeFieldType
  options?: string[]
}

const STEPEN_PODDERZHKI: AttributeFieldDef = {
  key: "stepen_podderzhki",
  label: "Степень поддержки",
  type: "select",
  options: ["Низкая", "Средняя", "Высокая"],
}

const FORMA_CHASHKI: AttributeFieldDef = {
  key: "forma_chashki",
  label: "Форма чашки",
  type: "select",
  options: ["Без формованной чашки", "Pull-on", "Формованная", "Push-up"],
}

const REGULIROVKA: AttributeFieldDef = {
  key: "regulirovka",
  label: "Регулировка",
  type: "select",
  options: [
    "Без регулировки",
    "Регулируемые бретели",
    "Регулируемая застёжка",
  ],
}

const ZASTEZHKA: AttributeFieldDef = {
  key: "zastezhka",
  label: "Застёжка",
  type: "select",
  options: ["Без застёжки", "Крючки", "Застёжка спереди", "Магнитная"],
}

const DLYA_KAKOY_GRUDI: AttributeFieldDef = {
  key: "dlya_kakoy_grudi",
  label: "Для какой груди",
  type: "select",
  options: ["Для любой", "Малая/средняя", "Средняя/большая", "Большая"],
}

const POSADKA_TRUSOV: AttributeFieldDef = {
  key: "posadka_trusov",
  label: "Посадка трусов",
  type: "select",
  options: ["Низкая", "Средняя", "Высокая"],
}

const VID_TRUSOV: AttributeFieldDef = {
  key: "vid_trusov",
  label: "Вид трусов",
  type: "select",
  options: ["Слипы", "Бразилианы", "Хипстеры", "Стринги", "Танга", "Шортики"],
}

const NAZNACHENIE: AttributeFieldDef = {
  key: "naznachenie",
  label: "Назначение",
  type: "select",
  options: ["Повседневное", "Спорт", "Премиум", "Сон"],
}

const STIL: AttributeFieldDef = { key: "stil", label: "Стиль", type: "text" }

const PO_NASTROENIYU: AttributeFieldDef = {
  key: "po_nastroeniyu",
  label: "По настроению",
  type: "text",
}

/** Полный реестр всех известных атрибутов (для динамических форм). */
export const ALL_ATTRIBUTES: Record<string, AttributeFieldDef> = {
  stepen_podderzhki: STEPEN_PODDERZHKI,
  forma_chashki: FORMA_CHASHKI,
  regulirovka: REGULIROVKA,
  zastezhka: ZASTEZHKA,
  dlya_kakoy_grudi: DLYA_KAKOY_GRUDI,
  posadka_trusov: POSADKA_TRUSOV,
  vid_trusov: VID_TRUSOV,
  naznachenie: NAZNACHENIE,
  stil: STIL,
  po_nastroeniyu: PO_NASTROENIYU,
}

/**
 * `kategoriya_id` → массив атрибутов, отображаемых в карточке модели.
 *
 * @deprecated W2.2: маппинг перенесён в таблицу `kategoriya_atributy`
 *   (migration 016). UI читает связи через `fetchAttributesForCategory(id)`,
 *   а описания полей (label / type / options) — через `ALL_ATTRIBUTES`.
 *   Эта константа сохранена как fallback / документация до W6.1, в котором
 *   AttributeFieldDef registry тоже уедет в БД (таблица `atributy`).
 *
 * MVP покрывал 5 категорий (id 1–5 в моке). Здесь сопоставлено с
 * реальными id из БД (см. таблицу `kategorii`):
 *   1  Комплект белья  →  все базовые атрибуты
 *   2  Трусы           →  трусы + общие
 *   3  Боди            →  верх + общие
 *   4  Леггинсы        →  спортивные общие         // TODO Wave 2: уточнить
 *   5  Лонгслив        →  спортивные общие         // TODO Wave 2: уточнить
 *   6  Рашгард         →  спортивные общие         // TODO Wave 2: уточнить
 *   7  Топ             →  верх + общие
 *   8  Футболка        →  спортивные общие         // TODO Wave 2: уточнить
 *   10 Велосипедки     →  спортивные общие         // TODO Wave 2: уточнить
 *   11 Бюстгалтер      →  верх (бра) + общие
 */
export const ATTRIBUTES_BY_CATEGORY: Record<number, AttributeFieldDef[]> = {
  1: [
    STEPEN_PODDERZHKI,
    FORMA_CHASHKI,
    REGULIROVKA,
    ZASTEZHKA,
    DLYA_KAKOY_GRUDI,
    POSADKA_TRUSOV,
    VID_TRUSOV,
    NAZNACHENIE,
    STIL,
    PO_NASTROENIYU,
  ],
  2: [POSADKA_TRUSOV, VID_TRUSOV, NAZNACHENIE, STIL, PO_NASTROENIYU],
  3: [
    STEPEN_PODDERZHKI,
    FORMA_CHASHKI,
    DLYA_KAKOY_GRUDI,
    NAZNACHENIE,
    STIL,
    PO_NASTROENIYU,
  ],
  4: [NAZNACHENIE, STIL, PO_NASTROENIYU],
  5: [NAZNACHENIE, STIL, PO_NASTROENIYU],
  6: [NAZNACHENIE, STIL, PO_NASTROENIYU],
  7: [STEPEN_PODDERZHKI, NAZNACHENIE, STIL, PO_NASTROENIYU],
  8: [NAZNACHENIE, STIL, PO_NASTROENIYU],
  10: [NAZNACHENIE, STIL, PO_NASTROENIYU],
  11: [
    STEPEN_PODDERZHKI,
    FORMA_CHASHKI,
    REGULIROVKA,
    ZASTEZHKA,
    DLYA_KAKOY_GRUDI,
    NAZNACHENIE,
    STIL,
    PO_NASTROENIYU,
  ],
}

/**
 * Какое поле редактируется на каком уровне иерархии.
 * Скопировано из MVP (`wookiee_matrix_mvp_v4.jsx`, строки ~272–294).
 */
export const FIELD_LEVEL: Record<string, FieldLevel> = {
  // Модель (modeli_osnova)
  kod: "model",
  brand_id: "model",
  kategoriya_id: "model",
  kollekciya_id: "model",
  fabrika_id: "model",
  tip_kollekcii: "model",
  tip_kollekcii_id: "model",
  material: "model",
  sostav_syrya: "model",
  composition: "model",
  razmery_modeli: "model",
  kratnost_koroba: "model",
  ves_kg: "model",
  dlina_cm: "model",
  shirina_cm: "model",
  vysota_cm: "model",
  srok_proizvodstva: "model",
  sku_china: "model",
  tnved: "model",
  gruppa_sertifikata: "model",
  notion_link: "model",
  notion_strategy_link: "model",
  yandex_disk_link: "model",
  upakovka_id: "model",
  // Атрибуты — на уровне модели
  stepen_podderzhki: "model",
  forma_chashki: "model",
  regulirovka: "model",
  zastezhka: "model",
  dlya_kakoy_grudi: "model",
  posadka_trusov: "model",
  vid_trusov: "model",
  naznachenie: "model",
  stil: "model",
  po_nastroeniyu: "model",
  // Контент — на уровне модели
  nazvanie_etiketka: "model",
  nazvanie_sayt: "model",
  opisanie_sayt: "model",
  tegi: "model",

  // Вариация (modeli)
  importer_id: "variation",
  artikul_modeli: "variation",
  nabor: "variation",
  rossiyskiy_razmer: "variation",

  // Артикул (artikuly)
  cvet_id: "artikul",
  nomenklatura_wb: "artikul",
  artikul_ozon: "artikul",

  // SKU (tovary)
  barkod: "sku",
  razmer_id: "sku",
  sku_china_size: "sku",
  status_obshiy: "sku",
  status_ozon: "sku",
  status_sayt: "sku",
  status_lamoda: "sku",
  ozon_product_id: "sku",
  ozon_fbo_sku_id: "sku",
  lamoda_seller_sku: "sku",
}
