import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createBrandQuery,
  createSubstituteArticle,
  fetchSearchQueries,
  fetchSearchQueryStats,
  fetchSearchQueryWeekly,
  updateSearchQueryStatus,
  type BrandQueryCreate,
  type SubstituteArticleCreate,
} from '@/api/marketing/search-queries'
import type { SearchQueryRow, SearchQueryStatus } from '@/types/marketing'

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

export function useUpdateSearchQueryStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ unifiedId, status }: { unifiedId: string; status: SearchQueryStatus }) =>
      updateSearchQueryStatus(unifiedId, status),
    onMutate: async ({ unifiedId, status }) => {
      await qc.cancelQueries({ queryKey: searchQueriesKeys.list() })
      const prev = qc.getQueryData<SearchQueryRow[]>(searchQueriesKeys.list()) ?? []
      const next = prev.map((r) => (r.unified_id === unifiedId ? { ...r, status } : r))
      qc.setQueryData(searchQueriesKeys.list(), next)
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(searchQueriesKeys.list(), ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}

function deriveGroupKind(purpose: string, campaign_name?: string | null): SearchQueryRow['group_kind'] {
  if (purpose === 'creators' && /^креатор[_ ]/i.test(campaign_name ?? '')) return 'cr_personal'
  if (purpose === 'creators') return 'cr_general'
  return 'external'
}

function deriveCreatorRef(purpose: string, campaign_name?: string | null): string | null {
  if (purpose === 'creators' && campaign_name) {
    const m = campaign_name.match(/^креатор[_ ](.+)$/i)
    return m ? m[1].trim() : null
  }
  return null
}

export function useCreateSubstituteArticle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createSubstituteArticle,
    onMutate: async (input: SubstituteArticleCreate) => {
      await qc.cancelQueries({ queryKey: searchQueriesKeys.list() })
      const prev = qc.getQueryData<SearchQueryRow[]>(searchQueriesKeys.list()) ?? []
      const code = input.code.trim()
      const optimistic: SearchQueryRow = {
        unified_id: 'S-' + Date.now(),
        source_id: -Date.now(),
        source_table: 'substitute_articles',
        group_kind: deriveGroupKind(input.purpose, input.campaign_name),
        query_text: code,
        artikul_id: input.artikul_id,
        nomenklatura_wb: input.nomenklatura_wb ?? null,
        ww_code: code.startsWith('WW') ? code : null,
        campaign_name: input.campaign_name?.trim() ?? null,
        purpose: input.purpose,
        model_hint: null,
        creator_ref: deriveCreatorRef(input.purpose, input.campaign_name),
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      qc.setQueryData<SearchQueryRow[]>(searchQueriesKeys.list(), [optimistic, ...prev])
      return { prev }
    },
    onError: (_err: unknown, _input: SubstituteArticleCreate, ctx?: { prev: SearchQueryRow[] }) => {
      if (ctx?.prev) qc.setQueryData(searchQueriesKeys.list(), ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}
