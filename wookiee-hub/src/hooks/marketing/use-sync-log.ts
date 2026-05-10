import { useQuery } from '@tanstack/react-query'
import { fetchLastSync } from '@/api/marketing/sync-log'

export const syncLogKeys = {
  last: (jobName: string) => ['marketing', 'sync-log', jobName] as const,
}

export function useLastSync(jobName: string) {
  return useQuery({
    queryKey: syncLogKeys.last(jobName),
    queryFn: () => fetchLastSync(jobName),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    refetchOnWindowFocus: true,
  })
}
