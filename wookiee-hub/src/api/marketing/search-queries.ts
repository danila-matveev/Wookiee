import { supabase } from '@/lib/supabase'
import type {
  SearchQueryRow,
  SearchQueryStatsAgg,
  SearchQueryWeeklyStat,
  SearchQueryProductBreakdownRow,
} from '@/types/marketing'
import { STATUS_UI_TO_DB, type StatusUI } from '@/types/marketing'

export interface SubstituteArticleCreate {
  code: string
  artikul_id: number
  purpose: string                       // Russian "Назначение" from Sheets (Яндекс/Таргет ВК/Adblogger/креаторы/соцсети бренда/блогеры/Telega.in/паблики инст и тг)
  nomenklatura_wb?: string | null
  sku_label?: string | null             // denormalized article name (Wendy/white)
  campaign_name?: string | null         // creator_ref auto-derived by trigger
}

export async function createSubstituteArticle(input: SubstituteArticleCreate): Promise<void> {
  const code = input.code.trim()
  const entityType = /^WW\d+/i.test(code) ? 'ww' : 'nm_id'
  const wwCode = entityType === 'ww' ? code : null

  const { error } = await supabase.schema('crm').from('substitute_articles').insert({
    code,
    query_text: code,
    ww_code: wwCode,
    artikul_id: input.artikul_id,
    purpose: input.purpose,
    nomenklatura_wb: input.nomenklatura_wb ?? (entityType === 'nm_id' ? code : null),
    sku_label: input.sku_label ?? null,
    campaign_name: input.campaign_name?.trim() || null,
    entity_type: entityType,
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

/**
 * Per-product breakdown: which WB nm_ids were opened/added-to-cart/ordered when users
 * searched for a given query (brand word, nm_id, or WW-code).
 * Source: marketing.search_query_product_breakdown (filled by ETL from WB analytics).
 *
 * For each entity_type we filter by different search_word value:
 * - brand: query_text (the brand keyword)
 * - nm_id: query_text (the nm_id as text matches search_word)
 * - ww: query_text (WW-code as it appears in WB substitution analytics)
 */
export async function fetchSearchQueryProductBreakdown(
  searchWord: string,
  from: string,
  to: string,
): Promise<SearchQueryProductBreakdownRow[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_query_product_breakdown')
    .select('*')
    .eq('search_word', searchWord)
    .gte('week_start', from)
    .lte('week_start', to)
    .order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    week_start: r.week_start as string,
    search_word: r.search_word as string,
    nm_id: r.nm_id as number,
    artikul_id: r.artikul_id == null ? null : (r.artikul_id as number),
    sku_label: r.sku_label as string,
    model_code: r.model_code == null ? null : (r.model_code as string),
    open_card: Number(r.open_card ?? 0),
    add_to_cart: Number(r.add_to_cart ?? 0),
    orders: Number(r.orders ?? 0),
  }))
}

export async function fetchSearchQueryWeekly(substituteArticleId: number): Promise<SearchQueryWeeklyStat[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_query_stats_weekly')
    .select('*').eq('search_query_id', substituteArticleId)
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as SearchQueryWeeklyStat[]
}

/**
 * Weekly stats keyed by raw WB Analytics search_word.
 * Mirrors the JOIN logic of marketing.search_query_stats_aggregated v3
 * (search_word = query_text OR nomenklatura_wb), giving brands, nm_ids and
 * WW-codes a single unified source of weekly metrics.
 *
 * Field rename: open_card → transitions, add_to_cart → additions
 * to match the SearchQueryWeeklyStat shape used by the UI.
 */
export async function fetchSearchQueryWeeklyByWord(
  searchWord: string,
  nomenklaturaWb: string | null,
): Promise<SearchQueryWeeklyStat[]> {
  // .in() over .or() — каждое значение шлётся отдельным URL-параметром,
  // не склеивается строкой → безопасно для значений с «,», пробелами, «/».
  const words = nomenklaturaWb && nomenklaturaWb !== searchWord
    ? [searchWord, nomenklaturaWb]
    : [searchWord]
  const { data, error } = await supabase
    .schema('marketing').from('search_queries_weekly')
    .select('search_word, week_start, frequency, open_card, add_to_cart, orders')
    .in('search_word', words)
    .order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    search_query_id: -1, // not applicable when aggregating by raw search_word
    week_start: r.week_start as string,
    frequency: Number(r.frequency ?? 0),
    transitions: Number(r.open_card ?? 0),
    additions: Number(r.add_to_cart ?? 0),
    orders: Number(r.orders ?? 0),
  }))
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
