// useTableSort — generic click-to-sort hook for catalog tables (W8.1).
//
// Cycle on each click of the SAME column: asc → desc → null (no sort).
// Clicking a DIFFERENT column starts again at asc.
//
// `sortRows` takes either:
//   - a row[col] lookup (default), or
//   - a custom `getValue(row, col)` resolver for derived/computed columns.
//
// Number vs. string is detected by typeof; strings are compared with
// `localeCompare('ru', { numeric: true, sensitivity: 'base' })` so codes
// like `MOD10` < `MOD2` sort intuitively.

import { useCallback, useState } from "react"

export type SortDirection = "asc" | "desc" | null

export interface SortState<K extends string> {
  column: K | null
  direction: SortDirection
}

export function useTableSort<K extends string>(
  initialColumn: K | null = null,
  initialDir: SortDirection = null,
) {
  const [sort, setSort] = useState<SortState<K>>({
    column: initialColumn,
    direction: initialDir,
  })

  /** Cycle asc → desc → null on each click of the same column. */
  const toggleSort = useCallback((column: K) => {
    setSort((prev) => {
      if (prev.column !== column) return { column, direction: "asc" }
      if (prev.direction === "asc") return { column, direction: "desc" }
      return { column: null, direction: null }
    })
  }, [])

  /** Set sort externally (e.g. hydrating from ui_preferences). */
  const setSortState = useCallback((next: SortState<K>) => {
    setSort(next)
  }, [])

  const sortRows = useCallback(
    <T extends Record<string, unknown>>(
      rows: T[],
      getValue?: (row: T, col: K) => unknown,
    ): T[] => {
      if (sort.column == null || sort.direction == null) return rows
      const col = sort.column
      const dir = sort.direction === "asc" ? 1 : -1
      const out = [...rows]
      out.sort((a, b) => {
        const va = getValue ? getValue(a, col) : (a as Record<string, unknown>)[col]
        const vb = getValue ? getValue(b, col) : (b as Record<string, unknown>)[col]
        if (va == null && vb == null) return 0
        if (va == null) return 1
        if (vb == null) return -1
        if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir
        return (
          String(va).localeCompare(String(vb), "ru", {
            numeric: true,
            sensitivity: "base",
          }) * dir
        )
      })
      return out
    },
    [sort],
  )

  return { sort, toggleSort, setSortState, sortRows }
}
