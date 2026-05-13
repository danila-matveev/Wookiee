import { supabase } from '@/lib/supabase'
import type { SearchQueryRow, SearchQueryStatsAgg, SearchQueryWeeklyStat } from '@/types/marketing'
import { STATUS_UI_TO_DB, type StatusUI } from '@/types/marketing'

export interface SubstituteArticleCreate {
  code: string
  artikul_id: number
  purpose: string                       // channel slug (validated against marketing.channels)
  nomenklatura_wb?: string | null
  campaign_name?: string | null         // creator_ref auto-derived by trigger
}

export async function createSubstituteArticle(input: SubstituteArticleCreate): Promise<void> {
  // Soft-validate channel slug
  const { data: ch, error: chErr } = await supabase
    .schema('marketing').from('channels')
    .select('slug').eq('slug', input.purpose).maybeSingle()
  if (chErr) throw chErr
  if (!ch) throw new Error(`Неизвестный канал: ${input.purpose}. Добавьте через справочник каналов.`)

  const { error } = await supabase.schema('crm').from('substitute_articles').insert({
    code: input.code.trim(),
    artikul_id: input.artikul_id,
    purpose: input.purpose,
    nomenklatura_wb: input.nomenklatura_wb ?? null,
    campaign_name: input.campaign_name?.trim() || null,
    status: 'active',
  })
  if (error) throw error
}

export interface BrandQueryCreate {
  query: string
  canonical_brand: string
  model_osnova_id?: number | null
  notes?: string
}

export async function createBrandQuery(input: BrandQueryCreate): Promise<void> {
  const { error } = await supabase.schema('crm').from('branded_queries').insert({
    query: input.query.trim(),
    canonical_brand: input.canonical_brand.trim().toLowerCase(),
    model_osnova_id: input.model_osnova_id ?? null,
    status: 'active',
    notes: input.notes ?? null,
  })
  if (error) throw error
}

export async function fetchSearchQueries(): Promise<SearchQueryRow[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_queries_unified')
    .select('*')
    .order('updated_at', { ascending: false, nullsFirst: false })
  if (error) throw error
  return (data ?? []) as SearchQueryRow[]
}

export async function fetchSearchQueryStats(from: string, to: string): Promise<SearchQueryStatsAgg[]> {
  const { data, error } = await supabase
    .schema('marketing').rpc('search_query_stats_aggregated', { p_from: from, p_to: to })
  if (error) throw error
  return (data ?? []) as SearchQueryStatsAgg[]
}

export async function fetchSearchQueryWeekly(substituteArticleId: number): Promise<SearchQueryWeeklyStat[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_query_stats_weekly')
    .select('*').eq('search_query_id', substituteArticleId)
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as SearchQueryWeeklyStat[]
}

export async function updateSearchQueryStatus(
  source: 'branded_queries' | 'substitute_articles',
  id: number,
  statusUI: StatusUI,
): Promise<void> {
  const statusDB = STATUS_UI_TO_DB[statusUI]
  // source tables (branded_queries, substitute_articles) live in the crm schema
  const { error } = await supabase
    .schema('crm').from(source)
    .update({ status: statusDB, updated_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw new Error(error.message)
}
