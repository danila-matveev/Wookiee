import { supabase } from '@/lib/supabase'

export interface ModeliRow { id: number; nazvanie: string; kod: string | null }
export interface ArtikulRow { id: number; artikul: string; nomenklatura_wb: number | null; color_label: string | null }

export async function fetchModeli(): Promise<ModeliRow[]> {
  const { data, error } = await supabase
    .from('modeli')                       // public schema; supabase JS uses public by default
    .select('id, nazvanie, kod')
    .order('nazvanie')
  if (error) throw error
  return (data ?? []) as ModeliRow[]
}

export async function fetchArtikulyForModel(modelId: number): Promise<ArtikulRow[]> {
  const { data, error } = await supabase
    .from('artikuly')
    .select('id, artikul, nomenklatura_wb, cveta(color)')
    .eq('model_id', modelId)
    .not('nomenklatura_wb', 'is', null)
    .order('artikul')
  if (error) throw error
  return ((data ?? []) as unknown as Array<{ id: number; artikul: string; nomenklatura_wb: number | null; cveta: { color: string | null } | { color: string | null }[] | null }>)
    .map((r) => {
      const cvetaColor = Array.isArray(r.cveta) ? r.cveta[0]?.color ?? null : r.cveta?.color ?? null
      return { id: r.id, artikul: r.artikul, nomenklatura_wb: r.nomenklatura_wb, color_label: cvetaColor }
    })
}
