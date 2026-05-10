import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createBrandQuery, fetchSearchQueries, fetchSearchQueryStats, fetchSearchQueryWeekly, type BrandQueryCreate } from '@/api/marketing/search-queries'
import type { SearchQueryRow } from '@/types/marketing'

export const searchQueriesKeys = {
  all:    ['marketing', 'search-queries'] as const,
  list:   () => [...searchQueriesKeys.all, 'list'] as const,
  stats:  (from: string, to: string) => [...searchQueriesKeys.all, 'stats', from, to] as const,
  weekly: (id: number) => [...searchQueriesKeys.all, 'weekly', id] as const,
}

export function useSearchQueries() {
  return useQuery({ queryKey: searchQueriesKeys.list(), queryFn: fetchSearchQueries, staleTime: 5 * 60_000 })
}
export function useSearchQueryStats(from: string, to: string) {
  return useQuery({
    queryKey: searchQueriesKeys.stats(from, to),
    queryFn: () => fetchSearchQueryStats(from, to),
    staleTime: 60_000,
    enabled: Boolean(from && to),
  })
}
export function useSearchQueryWeekly(substituteArticleId: number | null) {
  return useQuery({
    queryKey: searchQueriesKeys.weekly(substituteArticleId ?? -1),
    queryFn: () => fetchSearchQueryWeekly(substituteArticleId!),
    staleTime: 60_000,
    enabled: substituteArticleId != null,
  })
}

export function useCreateBrandQuery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createBrandQuery,
    onMutate: async (input: BrandQueryCreate) => {
      await qc.cancelQueries({ queryKey: searchQueriesKeys.list() })
      const prev = qc.getQueryData<SearchQueryRow[]>(searchQueriesKeys.list()) ?? []
      const optimistic: SearchQueryRow = {
        unified_id: 'B-' + Date.now(),
        source_id: -Date.now(),
        source_table: 'branded_queries',
        group_kind: 'brand',
        query_text: input.query.trim(),
        model_hint: input.canonical_brand.trim().toLowerCase(),
        artikul_id: null,
        nomenklatura_wb: null,
        ww_code: null,
        campaign_name: null,
        purpose: null,
        creator_ref: null,
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      qc.setQueryData<SearchQueryRow[]>(searchQueriesKeys.list(), [optimistic, ...prev])
      return { prev }
    },
    onError: (_err: unknown, _input: BrandQueryCreate, ctx?: { prev: SearchQueryRow[] }) => {
      if (ctx?.prev) qc.setQueryData(searchQueriesKeys.list(), ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}
