// W9.12 — Filter color palette by category.
//
// Returns colours filtered by `kategoriyaId`:
//   - if `kategoriyaId == null` → return ALL colours from `cveta`.
//   - if `kategoriyaId` set → return colours that are either:
//       (a) explicitly linked to this category in `cvet_kategoriya`, OR
//       (b) have NO rows in `cvet_kategoriya` at all (legacy fallback —
//           untagged colours are visible everywhere until they get classified).
//
// Single fetch, in-memory filter — `cveta` has ~50 rows, no point in
// server-side JOINs.

import { useQuery } from "@tanstack/react-query"

import { fetchCvetaWithUsage, type CvetRow } from "@/lib/catalog/service"
import { supabase } from "@/lib/supabase"

interface CvetKategoriyaLink {
  cvet_id: number
  kategoriya_id: number
}

async function fetchCvetKategoriyaLinks(): Promise<CvetKategoriyaLink[]> {
  const { data, error } = await supabase
    .from("cvet_kategoriya")
    .select("cvet_id, kategoriya_id")
  if (error) throw error
  return (data ?? []) as CvetKategoriyaLink[]
}

export interface AvailableColorsResult {
  colors: CvetRow[]
  isLoading: boolean
  isError: boolean
  error: unknown
}

/**
 * Public hook: returns colours applicable to a given category.
 */
export function useAvailableColors(kategoriyaId: number | null | undefined): AvailableColorsResult {
  const cvetaQ = useQuery({
    queryKey: ["catalog", "cveta-with-usage"],
    queryFn: fetchCvetaWithUsage,
    staleTime: 5 * 60 * 1000,
  })

  const linksQ = useQuery({
    queryKey: ["catalog", "cvet-kategoriya-links"],
    queryFn: fetchCvetKategoriyaLinks,
    staleTime: 5 * 60 * 1000,
  })

  const allColors = cvetaQ.data ?? []
  const links = linksQ.data ?? []

  // No filter requested → return everything.
  if (kategoriyaId == null) {
    return {
      colors: allColors,
      isLoading: cvetaQ.isLoading,
      isError: cvetaQ.isError,
      error: cvetaQ.error,
    }
  }

  // Build: which colours have at least one tag, and which match this category.
  const cvetIdsWithAnyTag = new Set<number>()
  const cvetIdsForThisCategory = new Set<number>()
  for (const link of links) {
    cvetIdsWithAnyTag.add(link.cvet_id)
    if (link.kategoriya_id === kategoriyaId) {
      cvetIdsForThisCategory.add(link.cvet_id)
    }
  }

  const filtered = allColors.filter((c) =>
    cvetIdsForThisCategory.has(c.id) || !cvetIdsWithAnyTag.has(c.id),
  )

  return {
    colors: filtered,
    isLoading: cvetaQ.isLoading || linksQ.isLoading,
    isError: cvetaQ.isError || linksQ.isError,
    error: cvetaQ.error ?? linksQ.error,
  }
}
