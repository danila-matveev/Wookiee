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
