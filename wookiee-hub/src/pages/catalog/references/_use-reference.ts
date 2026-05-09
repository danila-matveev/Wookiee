import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

/**
 * Read-only hook — fetch reference table.
 *
 * Backwards-compatible signature, retained because some pages already depend
 * on it (statusy.tsx, etc).
 */
export function useReference<T>(key: string, fetcher: () => Promise<T[]>) {
  return useQuery<T[], Error>({
    queryKey: ["catalog", "reference", key],
    queryFn: fetcher,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Full CRUD hook — bundles fetch + insert + update + delete with automatic
 * cache invalidation.
 *
 * Each reference page boils down to:
 *   const ref = useReferenceCrud<MyType>("upakovki", fetchUpakovki, {
 *     insert: insertUpakovka,
 *     update: updateUpakovka,
 *     remove: deleteUpakovka,
 *   })
 *
 * `ref.list.data`        — array
 * `ref.list.isLoading`   — boolean
 * `ref.list.error`       — Error | null
 * `ref.insert.mutateAsync(payload)`
 * `ref.update.mutateAsync({ id, patch })`
 * `ref.remove.mutateAsync(id)`
 */
export function useReferenceCrud<T, Payload = Record<string, unknown>>(
  key: string,
  fetcher: () => Promise<T[]>,
  mutations: {
    insert: (data: Payload) => Promise<unknown>
    update: (id: number, patch: Partial<Payload>) => Promise<unknown>
    remove: (id: number) => Promise<unknown>
  },
) {
  const qc = useQueryClient()
  const queryKey = ["catalog", "reference", key]

  const list = useQuery<T[], Error>({
    queryKey,
    queryFn: fetcher,
    staleTime: 5 * 60 * 1000,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey })

  const insert = useMutation({
    mutationFn: (data: Payload) => mutations.insert(data),
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Payload> }) =>
      mutations.update(id, patch),
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (id: number) => mutations.remove(id),
    onSuccess: invalidate,
  })

  return { list, insert, update, remove }
}
