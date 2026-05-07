import { supabase } from "@/lib/supabase"
import type { ModelOsnova } from "@/types/catalog"
import { computeCompleteness } from "./color-utils"

// ─── Basic reference fetchers ──────────────────────────────────────────────

export async function fetchKategorii() {
  const { data, error } = await supabase
    .from("kategorii")
    .select("id, nazvanie, opisanie")
    .order("id")
  if (error) throw error
  return data as { id: number; nazvanie: string; opisanie: string | null }[]
}

export async function fetchKollekcii() {
  const { data, error } = await supabase
    .from("kollekcii")
    .select("id, nazvanie, opisanie, god_zapuska")
    .order("nazvanie")
  if (error) throw error
  return data as { id: number; nazvanie: string; opisanie: string | null; god_zapuska: number | null }[]
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

export async function fetchRazmery() {
  const { data, error } = await supabase
    .from("razmery")
    .select("id, nazvanie, poryadok, ru, eu, china")
    .order("poryadok")
  if (error) throw error
  return data as {
    id: number
    nazvanie: string
    poryadok: number
    ru: string | null
    eu: string | null
    china: string | null
  }[]
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

// ─── Matrix list (modeli_osnova with aggregated counts) ────────────────────

export interface MatrixRow {
  id: number
  kod: string
  nazvanie_sayt: string | null
  tip_kollekcii: string | null
  kategoriya_id: number | null
  kategoriya: string | null
  kollekciya: string | null
  fabrika: string | null
  status_id: number | null
  updated_at: string | null
  modeli_cnt: number
  artikuly_cnt: number
  tovary_cnt: number
  cveta_cnt: number
  completeness: number
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
      kollekciya_id, fabrika_id, status_id,
      kategorii(nazvanie),
      kollekcii(nazvanie),
      fabriki(nazvanie),
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
      tip_kollekcii: mo.tip_kollekcii,
      kategoriya_id: mo.kategoriya_id,
      kategoriya: mo.kategorii?.nazvanie ?? null,
      kollekciya: mo.kollekcii?.nazvanie ?? null,
      fabrika: mo.fabriki?.nazvanie ?? null,
      status_id: mo.status_id,
      updated_at: mo.updated_at,
      modeli_cnt: modeli.length,
      artikuly_cnt: artikuly.length,
      tovary_cnt: tovary.length,
      cveta_cnt: cvetaIds.size,
      completeness: computeCompleteness(mo),
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
  semeystvo: string | null
  status_id: number | null
  created_at: string | null
  updated_at: string | null
  artikuly_cnt: number
  modeli_cnt: number
}

export async function fetchCvetaWithUsage(): Promise<CvetRow[]> {
  const [cvetaRes, artikulyRes] = await Promise.all([
    supabase
      .from("cveta")
      .select("id, color_code, cvet, color, lastovica, semeystvo, status_id, created_at, updated_at")
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
  tovary_cnt: number
}

export interface ColorDetail extends CvetRow {
  artikuly: ColorDetailArtikul[]
}

export async function fetchColorDetail(id: number): Promise<ColorDetail | null> {
  const [cvetRes, artikulyRes] = await Promise.all([
    supabase
      .from("cveta")
      .select("id, color_code, cvet, color, lastovica, semeystvo, status_id, created_at, updated_at")
      .eq("id", id)
      .single(),
    supabase
      .from("artikuly")
      .select(`
        id, artikul, nomenklatura_wb,
        modeli(
          id, kod, model_osnova_id,
          modeli_osnova(id, kod, tip_kollekcii, kategorii(nazvanie))
        ),
        tovary(id)
      `)
      .eq("cvet_id", id),
  ])

  if (cvetRes.error) {
    if (cvetRes.error.code === "PGRST116") return null
    throw cvetRes.error
  }
  if (artikulyRes.error) throw artikulyRes.error

  const cvet = cvetRes.data as any
  const rawArts = (artikulyRes.data ?? []) as any[]

  const artikuly = rawArts.map((a) => ({
    id: a.id,
    artikul: a.artikul,
    model_kod: a.modeli?.kod ?? null,
    model_osnova_kod: a.modeli?.modeli_osnova?.kod ?? null,
    model_osnova_id: a.modeli?.model_osnova_id ?? null,
    kategoriya: a.modeli?.modeli_osnova?.kategorii?.nazvanie ?? null,
    tip_kollekcii: a.modeli?.modeli_osnova?.tip_kollekcii ?? null,
    nomenklatura_wb: a.nomenklatura_wb ?? null,
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

// ─── Skleyki ───────────────────────────────────────────────────────────────

export interface SkleykaRow {
  id: number
  nazvanie: string
  importer_id: number | null
  importer_nazvanie: string | null
  created_at: string | null
  updated_at: string | null
}

export async function fetchSkleykiWb(): Promise<SkleykaRow[]> {
  const { data, error } = await supabase
    .from("skleyki_wb")
    .select("id, nazvanie, importer_id, importery(nazvanie), created_at, updated_at")
    .order("nazvanie")
  if (error) throw error
  return (data as any[]).map((s) => ({
    id: s.id,
    nazvanie: s.nazvanie,
    importer_id: s.importer_id,
    importer_nazvanie: s.importery?.nazvanie ?? null,
    created_at: s.created_at,
    updated_at: s.updated_at,
  }))
}

export async function fetchSkleykiOzon(): Promise<SkleykaRow[]> {
  const { data, error } = await supabase
    .from("skleyki_ozon")
    .select("id, nazvanie, importer_id, importery(nazvanie), created_at, updated_at")
    .order("nazvanie")
  if (error) throw error
  return (data as any[]).map((s) => ({
    id: s.id,
    nazvanie: s.nazvanie,
    importer_id: s.importer_id,
    importer_nazvanie: s.importery?.nazvanie ?? null,
    created_at: s.created_at,
    updated_at: s.updated_at,
  }))
}

// ─── Artikuly registry ─────────────────────────────────────────────────────

export interface ArtikulRow {
  id: number
  artikul: string
  model_id: number | null
  model_kod: string | null
  model_osnova_id: number | null
  model_osnova_kod: string | null
  cvet_id: number | null
  cvet_color_code: string | null
  cvet_nazvanie: string | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  tovary_cnt: number
  kategoriya: string | null
  kollekciya: string | null
  fabrika: string | null
}

export async function fetchArtikulyRegistry(): Promise<ArtikulRow[]> {
  const { data, error } = await supabase
    .from("artikuly")
    .select(`
      id, artikul, model_id, cvet_id, status_id, nomenklatura_wb, artikul_ozon,
      cveta(color_code, cvet),
      modeli(
        id, kod, model_osnova_id,
        modeli_osnova(
          id, kod, tip_kollekcii,
          kategorii(nazvanie),
          kollekcii(nazvanie),
          fabriki(nazvanie)
        )
      ),
      tovary(id)
    `)
    .order("artikul")
  if (error) throw error

  return (data as any[]).map((a) => ({
    id: a.id,
    artikul: a.artikul,
    model_id: a.model_id,
    model_kod: a.modeli?.kod ?? null,
    model_osnova_id: a.modeli?.model_osnova_id ?? null,
    model_osnova_kod: a.modeli?.modeli_osnova?.kod ?? null,
    cvet_id: a.cvet_id,
    cvet_color_code: a.cveta?.color_code ?? null,
    cvet_nazvanie: a.cveta?.cvet ?? null,
    status_id: a.status_id,
    nomenklatura_wb: a.nomenklatura_wb,
    artikul_ozon: a.artikul_ozon,
    tovary_cnt: (a.tovary ?? []).length,
    kategoriya: a.modeli?.modeli_osnova?.kategorii?.nazvanie ?? null,
    kollekciya: a.modeli?.modeli_osnova?.kollekcii?.nazvanie ?? null,
    fabrika: a.modeli?.modeli_osnova?.fabriki?.nazvanie ?? null,
  }))
}

// ─── Tovary registry ───────────────────────────────────────────────────────

export interface TovarRow {
  id: number
  barkod: string
  artikul_id: number | null
  artikul: string | null
  model_kod: string | null
  model_osnova_kod: string | null
  cvet_color_code: string | null
  razmer: string | null
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
}

export async function fetchTovaryRegistry(): Promise<TovarRow[]> {
  const { data, error } = await supabase
    .from("tovary")
    .select(`
      id, barkod, artikul_id, razmer_id, status_id, status_ozon_id, status_sayt_id,
      status_lamoda_id, sku_china_size, ozon_product_id, ozon_fbo_sku_id, lamoda_seller_sku,
      razmery(nazvanie),
      artikuly(
        artikul, nomenklatura_wb, artikul_ozon, cvet_id,
        cveta(color_code),
        modeli(
          kod, model_osnova_id,
          modeli_osnova(kod)
        )
      )
    `)
    .order("id")
    .range(0, 4999)
  if (error) throw error

  return (data as any[]).map((t) => ({
    id: t.id,
    barkod: t.barkod,
    artikul_id: t.artikul_id,
    artikul: t.artikuly?.artikul ?? null,
    model_kod: t.artikuly?.modeli?.kod ?? null,
    model_osnova_kod: t.artikuly?.modeli?.modeli_osnova?.kod ?? null,
    cvet_color_code: t.artikuly?.cveta?.color_code ?? null,
    razmer: t.razmery?.nazvanie ?? null,
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
  }))
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

// ─── Modeli operations (create / update / duplicate / archive cascade) ────

export interface ModelOsnovaPayload {
  kod: string
  kategoriya_id?: number | null
  kollekciya_id?: number | null
  fabrika_id?: number | null
  status_id?: number | null
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

/**
 * Bulk-update status of tovary rows (addressed by barkod) on a specific channel.
 * Channel determines which status field is updated:
 *   wb     → status_id
 *   ozon   → status_ozon_id
 *   sayt   → status_sayt_id
 *   lamoda → status_lamoda_id
 */
export async function bulkUpdateTovaryStatus(
  barkods: string[],
  statusId: number,
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
  skus: number
  colors: number
  skleyki_wb: number
  skleyki_ozon: number
  kategorii: number
  kollekcii: number
  fabriki: number
  importery: number
  razmery: number
  semeystva_cvetov: number
  upakovki: number
  kanaly_prodazh: number
  sertifikaty: number
  statusy: number
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
  const tables: (keyof CatalogCounts)[] = [
    "models",
    "variations",
    "articles",
    "skus",
    "colors",
    "skleyki_wb",
    "skleyki_ozon",
    "kategorii",
    "kollekcii",
    "fabriki",
    "importery",
    "razmery",
    "semeystva_cvetov",
    "upakovki",
    "kanaly_prodazh",
    "sertifikaty",
    "statusy",
  ]
  const tableMap: Record<keyof CatalogCounts, string> = {
    models: "modeli_osnova",
    variations: "modeli",
    articles: "artikuly",
    skus: "tovary",
    colors: "cveta",
    skleyki_wb: "skleyki_wb",
    skleyki_ozon: "skleyki_ozon",
    kategorii: "kategorii",
    kollekcii: "kollekcii",
    fabriki: "fabriki",
    importery: "importery",
    razmery: "razmery",
    semeystva_cvetov: "semeystva_cvetov",
    upakovki: "upakovki",
    kanaly_prodazh: "kanaly_prodazh",
    sertifikaty: "sertifikaty",
    statusy: "statusy",
  }
  const counts = await Promise.all(tables.map((k) => tableCount(tableMap[k])))
  const out = {} as CatalogCounts
  tables.forEach((k, i) => {
    out[k] = counts[i]
  })
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
