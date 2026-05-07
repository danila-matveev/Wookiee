// TypeScript interfaces matching the Supabase catalog schema

export interface Kategoriya {
  id: number
  nazvanie: string
}

export interface Kollekciya {
  id: number
  nazvanie: string
}

export interface Fabrika {
  id: number
  nazvanie: string
  strana: string | null
}

export interface Importer {
  id: number
  nazvanie: string
  nazvanie_en: string | null
  inn: string | null
  adres: string | null
}

export interface Razmer {
  id: number
  nazvanie: string
  poryadok: number
}

export type StatusTip = "model" | "product" | "color"

export interface Status {
  id: number
  nazvanie: string
  tip: StatusTip
}

export type ColorFamily = "tricot" | "jelly" | "audrey" | "sets" | "other"

export interface Cvet {
  id: number
  color_code: string
  cvet: string | null
  color: string | null
  lastovica: string | null
  semeystvo: ColorFamily | null
  status_id: number | null
  created_at: string | null
  updated_at: string | null
}

export type TipKollekcii =
  | "Трикотажное белье"
  | "Бесшовное белье Jelly"
  | "Бесшовное белье Audrey"

export interface ModelOsnova {
  id: number
  kod: string
  kategoriya_id: number | null
  kollekciya_id: number | null
  fabrika_id: number | null
  status_id: number | null
  tip_kollekcii: TipKollekcii | null
  material: string | null
  sostav_syrya: string | null
  composition: string | null
  razmery_modeli: string | null
  sku_china: string | null
  upakovka: string | null
  ves_kg: number | null
  dlina_cm: number | null
  shirina_cm: number | null
  vysota_cm: number | null
  kratnost_koroba: number | null
  srok_proizvodstva: string | null
  komplektaciya: string | null
  nazvanie_etiketka: string | null
  nazvanie_sayt: string | null
  opisanie_sayt: string | null
  details: string | null
  description: string | null
  tegi: string | null
  notion_link: string | null
  stepen_podderzhki: string | null
  forma_chashki: string | null
  regulirovka: string | null
  zastezhka: string | null
  dlya_kakoy_grudi: string | null
  posadka_trusov: string | null
  vid_trusov: string | null
  naznachenie: string | null
  stil: string | null
  po_nastroeniyu: string | null
  tnved: string | null
  gruppa_sertifikata: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Model {
  id: number
  kod: string
  nazvanie: string
  nazvanie_en: string | null
  artikul_modeli: string | null
  model_osnova_id: number | null
  importer_id: number | null
  status_id: number | null
  nabor: boolean | null
  rossiyskiy_razmer: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Artikul {
  id: number
  artikul: string
  model_id: number | null
  cvet_id: number | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Tovar {
  id: number
  barkod: string
  barkod_gs1: string | null
  barkod_gs2: string | null
  barkod_perehod: string | null
  artikul_id: number | null
  razmer_id: number | null
  status_id: number | null
  status_ozon_id: number | null
  status_sayt_id: number | null
  status_lamoda_id: number | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
  lamoda_seller_sku: string | null
  sku_china_size: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SkleykaWb {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
}

export interface SkleykaOzon {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
}
