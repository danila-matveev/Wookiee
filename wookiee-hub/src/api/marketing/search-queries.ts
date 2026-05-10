import { supabase } from '@/lib/supabase'
import type { SearchQueryRow, SearchQueryStatsAgg, SearchQueryWeeklyStat, SearchQueryStatus } from '@/types/marketing'
import { parseUnifiedId } from '@/lib/marketing-helpers'

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

export async function updateSearchQueryStatus(unifiedId: string, status: SearchQueryStatus): Promise<void> {
  const { source, id } = parseUnifiedId(unifiedId)
  const { error } = await supabase
    .schema('crm').from(source)
    .update({ status, updated_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw error
}
