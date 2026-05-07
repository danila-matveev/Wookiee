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
  kategoriya_id?: number | null
  kollekciya_id?: number | null
  fabrika_id?: number | null
  status_id?: number | null

  // Состав / производство
  tip_kollekcii?: string | null
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
