import { useQuery } from "@tanstack/react-query"

export function useReference<T>(key: string, fetcher: () => Promise<T[]>) {
  return useQuery<T[], Error>({
    queryKey: ["catalog", "reference", key],
    queryFn: fetcher,
    staleTime: 5 * 60 * 1000,
  })
}
