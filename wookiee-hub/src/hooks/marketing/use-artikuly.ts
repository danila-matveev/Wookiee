import { useQuery } from '@tanstack/react-query'
import { fetchModeli, fetchArtikulyForModel } from '@/api/marketing/artikuly'

export const artikulyKeys = {
  modeli: () => ['catalog', 'modeli'] as const,
  forModel: (modelId: number | null) => ['catalog', 'artikuly', modelId] as const,
}

export function useModeli() {
  return useQuery({ queryKey: artikulyKeys.modeli(), queryFn: fetchModeli, staleTime: 30 * 60_000 })
}

export function useArtikulyForModel(modelId: number | null) {
  return useQuery({
    queryKey: artikulyKeys.forModel(modelId),
    queryFn: () => fetchArtikulyForModel(modelId!),
    enabled: modelId != null,
    staleTime: 30 * 60_000,
  })
}
