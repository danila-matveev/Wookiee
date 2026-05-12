import { supabase } from '@/lib/supabase'

export interface SkuBrowserRow {
  model_id: number
  model_label: string
  model_code: string | null
  color_id: number
  color_label: string
  color_code: string | null
  razmer_id: number
  razmer_label: string
  razmer_order: number
  artikul_id: number
  artikul_label: string
  nomenklatura_wb: number | null
  tovar_id: number
  barcode: string | null
}

export async function fetchSkuBrowser(): Promise<SkuBrowserRow[]> {
  const { data, error } = await supabase
    .schema('marketing').from('sku_browser')
    .select('*')
  if (error) throw error
  return (data ?? []) as SkuBrowserRow[]
}
