import { useQuery } from '@tanstack/react-query'
import { fetchSearchQueries, fetchSearchQueryStats, fetchSearchQueryWeekly } from '@/api/marketing/search-queries'

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
