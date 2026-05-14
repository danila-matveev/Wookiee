import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createBrandQuery,
  createSubstituteArticle,
  fetchSearchQueries,
  fetchSearchQueryStats,
  fetchSearchQueryWeekly,
  fetchSearchQueryWeeklyByWord,
  fetchSearchQueryProductBreakdown,
  updateSearchQueryStatus,
  type BrandQueryCreate,
  type SubstituteArticleCreate,
} from '@/api/marketing/search-queries'
import type { SearchQueryRow, StatusUI } from '@/types/marketing'
import { STATUS_UI_TO_DB } from '@/types/marketing'
import { parseUnifiedId } from '@/lib/marketing-helpers'

export const searchQueriesKeys = {
  all:    ['marketing', 'search-queries'] as const,
  list:   () => [...searchQueriesKeys.all, 'list'] as const,
  stats:  (from: string, to: string) => [...searchQueriesKeys.all, 'stats', from, to] as const,
  weekly: (id: number) => [...searchQueriesKeys.all, 'weekly', id] as const,
  weeklyByWord: (sw: string, nm: string | null) =>
    [...searchQueriesKeys.all, 'weekly-by-word', sw, nm ?? ''] as const,
  productBreakdown: (sw: string, from: string, to: string) =>
    [...searchQueriesKeys.all, 'product-breakdown', sw, from, to] as const,
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

/**
 * Weekly stats by raw WB Analytics search_word — works uniformly for brands,
 * nm_ids and WW-codes. Mirrors the JOIN of search_query_stats_aggregated v3.
 */
export function useSearchQueryWeeklyByWord(searchWord: string | null, nomenklaturaWb: string | null) {
  return useQuery({
    queryKey: searchQueriesKeys.weeklyByWord(searchWord ?? '', nomenklaturaWb),
    queryFn: () => fetchSearchQueryWeeklyByWord(searchWord!, nomenklaturaWb),
    staleTime: 60_000,
    enabled: Boolean(searchWord),
  })
}

/** Per-product breakdown for a search query (brand word, nm_id, or WW-code). */
export function useSearchQueryProductBreakdown(searchWord: string | null, from: string, to: string) {
  return useQuery({
    queryKey: searchQueriesKeys.productBreakdown(searchWord ?? '', from, to),
    queryFn: () => fetchSearchQueryProductBreakdown(searchWord!, from, to),
    staleTime: 60_000,
    enabled: Boolean(searchWord && from && to),
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
        entity_type: 'brand',
        query_text: input.query.trim(),
        model_hint: input.canonical_brand.trim().toLowerCase(),
        artikul_id: null,
        nomenklatura_wb: null,
        sku_label: null,
        ww_code: null,
        campaign_name: null,
        purpose: 'брендированный запрос',
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
    mutationFn: ({ unifiedId, status }: { unifiedId: string; status: StatusUI }) => {
      const { source, id } = parseUnifiedId(unifiedId)
      return updateSearchQueryStatus(source, id, status)
    },
    onMutate: async ({ unifiedId, status }) => {
      await qc.cancelQueries({ queryKey: searchQueriesKeys.list() })
      const prev = qc.getQueryData<SearchQueryRow[]>(searchQueriesKeys.list()) ?? []
      // Rows hold DB-shaped status; convert UI→DB for optimistic update
      const statusDB = STATUS_UI_TO_DB[status]
      const next = prev.map((r) => (r.unified_id === unifiedId ? { ...r, status: statusDB } : r))
      qc.setQueryData(searchQueriesKeys.list(), next)
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(searchQueriesKeys.list(), ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}

function deriveEntityType(code: string): 'nm_id' | 'ww' {
  if (/^WW\d+/i.test(code)) return 'ww'
  return 'nm_id'
}

function deriveCreatorRef(purpose: string, campaign_name?: string | null): string | null {
  if (purpose === 'креаторы' && campaign_name) {
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
      const entityType = deriveEntityType(code)
      const optimistic: SearchQueryRow = {
        unified_id: 'S-' + Date.now(),
        source_id: -Date.now(),
        source_table: 'substitute_articles',
        entity_type: entityType,
        query_text: code,
        artikul_id: input.artikul_id,
        nomenklatura_wb: input.nomenklatura_wb ?? (entityType === 'nm_id' ? code : null),
        sku_label: input.sku_label ?? null,
        ww_code: entityType === 'ww' ? code : null,
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
