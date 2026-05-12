import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchSkuBrowser, type SkuBrowserRow } from '@/api/marketing/sku-browser'

export const skuBrowserKeys = {
  all: ['marketing', 'sku-browser'] as const,
}

export function useSkuBrowser() {
  return useQuery({
    queryKey: skuBrowserKeys.all,
    queryFn: fetchSkuBrowser,
    staleTime: 10 * 60_000,
  })
}

export interface ModelOption {
  id: number
  label: string
}
export interface ColorOption {
  id: number
  label: string
}
export interface SizeOption {
  id: number
  label: string
  order: number
}

export function useSkuCascade() {
  const q = useSkuBrowser()
  const rows: SkuBrowserRow[] = q.data ?? []

  const models: ModelOption[] = useMemo(() => {
    const seen = new Map<number, string>()
    for (const r of rows) if (!seen.has(r.model_id)) seen.set(r.model_id, r.model_label)
    return Array.from(seen, ([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label, 'ru'))
  }, [rows])

  const colorsForModel = (modelId: number | null): ColorOption[] => {
    if (modelId == null) return []
    const seen = new Map<number, string>()
    for (const r of rows) {
      if (r.model_id !== modelId) continue
      if (!seen.has(r.color_id)) seen.set(r.color_id, r.color_label)
    }
    return Array.from(seen, ([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label, 'ru'))
  }

  const sizesForModelColor = (modelId: number | null, colorId: number | null): SizeOption[] => {
    if (modelId == null || colorId == null) return []
    const seen = new Map<number, { label: string; order: number }>()
    for (const r of rows) {
      if (r.model_id !== modelId || r.color_id !== colorId) continue
      if (!seen.has(r.razmer_id)) seen.set(r.razmer_id, { label: r.razmer_label, order: r.razmer_order })
    }
    return Array.from(seen, ([id, v]) => ({ id, label: v.label, order: v.order })).sort((a, b) => a.order - b.order)
  }

  const matchedSku = (modelId: number | null, colorId: number | null, razmerId: number | null): SkuBrowserRow | null => {
    if (modelId == null || colorId == null || razmerId == null) return null
    return rows.find((r) => r.model_id === modelId && r.color_id === colorId && r.razmer_id === razmerId) ?? null
  }

  return {
    isLoading: q.isLoading,
    error:     q.error,
    models,
    colorsForModel,
    sizesForModelColor,
    matchedSku,
  }
}
