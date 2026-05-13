// W9.17 — Live lookup `statusy.id → { nazvanie, color, tip }`.
//
// Backed by the same React Query cache (`["statusy"]`) that every catalog page
// already populates via `fetchStatusy()`. Using one shared queryKey means:
//   - StatusBadge inside any page reuses the existing cache (no extra fetch),
//   - Mutations on `statusy` reference (W7.x) invalidate one key and every
//     badge re-renders.
//
// Why a dedicated hook: before W9.17 the `<StatusBadge statusId={…}>` API used
// a stale hardcoded fixture (`CATALOG_STATUSES`, ids 1–7) — for any other id it
// silently returned `null`, which broke W9.2 status columns. The hack was to
// pass a `resolveStatus` callback from every page. With this hook, the badge
// resolves on its own.
//
// Keep this hook tiny and synchronous-feeling: callers don't need
// loading-state plumbing for a 50-row reference table.

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import { fetchStatusy } from "@/lib/catalog/service"

export interface StatusyRow {
  id: number
  nazvanie: string
  tip: string
  color: string | null
}

export interface UseStatusyMapResult {
  /** id → row. Always a Map; empty until the first fetch resolves. */
  map: Map<number, StatusyRow>
  isLoading: boolean
  isError: boolean
}

/**
 * Returns `statusy` indexed by id. Shares the `["statusy"]` React Query cache.
 *
 * Usage:
 * ```tsx
 * const { map } = useStatusyMap()
 * const s = map.get(statusId)
 * ```
 *
 * Prefer `<StatusBadge statusId={…} />` for rendering — it calls this hook
 * internally and handles fallback / placeholder.
 */
export function useStatusyMap(): UseStatusyMapResult {
  const q = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 30 * 60 * 1000,
  })
  const map = useMemo(() => {
    const m = new Map<number, StatusyRow>()
    for (const s of q.data ?? []) m.set(s.id, s as StatusyRow)
    return m
  }, [q.data])
  return { map, isLoading: q.isLoading, isError: q.isError }
}
