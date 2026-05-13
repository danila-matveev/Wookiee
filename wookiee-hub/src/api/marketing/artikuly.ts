import { supabase } from '@/lib/supabase'

export interface ModeliRow { id: number; nazvanie: string; kod: string | null }

/**
 * Flattened artikul row keyed by (color × size). One artikuly DB row may expand into N entries
 * (one per `tovary.razmer_id`). `id` remains the color-level `artikuly.id` and is used as the
 * substitute_articles.artikul_id FK. `nm_id` (= nomenklatura_wb) and `color` come from the
 * artikul / cveta join; `size` is the razmery.nazvanie of the corresponding tovar.
 */
export interface ArtikulRow {
  id: number              // artikuly.id (color-level FK)
  artikul: string         // human-readable SKU code
  nm_id: number | null    // nomenklatura_wb
  color: string | null
  size: string | null
}

export async function fetchModeli(): Promise<ModeliRow[]> {
  const { data, error } = await supabase
    .from('modeli')
    .select('id, nazvanie, kod')
    .order('nazvanie')
  if (error) throw error
  return (data ?? []) as ModeliRow[]
}

interface RawArtikulRow {
  id: number
  artikul: string
  nomenklatura_wb: number | null
  cveta: { color: string | null } | { color: string | null }[] | null
  tovary: Array<{ razmery: { nazvanie: string | null } | { nazvanie: string | null }[] | null }> | null
}

export async function fetchArtikulyForModel(modelId: number): Promise<ArtikulRow[]> {
  const { data, error } = await supabase
    .from('artikuly')
    .select('id, artikul, nomenklatura_wb, cveta(color), tovary(razmery(nazvanie))')
    .eq('model_id', modelId)
    .not('nomenklatura_wb', 'is', null)
    .order('artikul')
  if (error) throw error
  const rows = (data ?? []) as unknown as RawArtikulRow[]
  const out: ArtikulRow[] = []
  for (const r of rows) {
    const color = Array.isArray(r.cveta) ? r.cveta[0]?.color ?? null : r.cveta?.color ?? null
    const tovary = r.tovary ?? []
    if (tovary.length === 0) {
      out.push({ id: r.id, artikul: r.artikul, nm_id: r.nomenklatura_wb, color, size: null })
      continue
    }
    for (const t of tovary) {
      const size = Array.isArray(t.razmery) ? t.razmery[0]?.nazvanie ?? null : t.razmery?.nazvanie ?? null
      out.push({ id: r.id, artikul: r.artikul, nm_id: r.nomenklatura_wb, color, size })
    }
  }
  return out
}
