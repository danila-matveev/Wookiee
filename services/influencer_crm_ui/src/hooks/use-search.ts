import { useQuery } from '@tanstack/react-query';
import { type SearchResponse, searchAll } from '@/api/search';

/**
 * Trigger a global search. Disabled until `q` has at least 2 characters —
 * single-letter queries are noisy and would still hit the BFF (server allows
 * `min_length=1`, but the UI debounces by gating instead of by timer because
 * the search is submit-driven, not type-as-you-go).
 */
export function useSearch(q: string) {
  const trimmed = q.trim();
  return useQuery<SearchResponse>({
    queryKey: ['search', trimmed],
    queryFn: () => searchAll(trimmed),
    enabled: trimmed.length >= 2,
  });
}
