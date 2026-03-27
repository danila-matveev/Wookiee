import { useState, useMemo, useCallback } from "react"

// ── Types ────────────────────────────────────────────────────────────────────

export interface TableSortState {
  field: string | null
  order: "asc" | "desc"
}

export interface TableState {
  page: number
  perPage: number
  sort: TableSortState
  hiddenFields: Set<string>
  setPage: (page: number) => void
  toggleSort: (field: string) => void
  toggleFieldVisibility: (field: string) => void
  apiParams: Record<string, string | number>
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Manages table pagination, sorting, and column visibility state.
 *
 * `apiParams` returns an object ready to spread into API fetch calls:
 * `{ page, per_page, sort?, order? }` — sort/order only included when active.
 */
/**
 * Default fields to hide per entity — only show key business columns initially.
 * Users can toggle visibility via "Настроить поля" popover.
 */
const DEFAULT_HIDDEN: Record<string, string[]> = {
  models: [
    "sku_china", "upakovka", "ves_kg", "dlina_cm", "shirina_cm", "vysota_cm",
    "kratnost_koroba", "srok_proizvodstva", "komplektaciya",
    "material", "sostav_syrya", "composition",
    "tnved", "gruppa_sertifikata",
    "nazvanie_etiketka", "nazvanie_sayt", "opisanie_sayt",
    "tegi", "notion_link",
    "created_at", "updated_at",
  ],
  articles: [],
  products: [],
}

export function useTableState(
  entity: string,
  defaultPerPage = 50,
): TableState {
  const [page, setPageRaw] = useState(1)
  const [perPage] = useState(defaultPerPage)
  const [sort, setSort] = useState<TableSortState>({ field: null, order: "asc" })
  const [hiddenFields, setHiddenFields] = useState<Set<string>>(
    () => new Set(DEFAULT_HIDDEN[entity] ?? []),
  )

  const setPage = useCallback((p: number) => {
    setPageRaw(p)
  }, [])

  const toggleSort = useCallback((field: string) => {
    setSort((prev) => {
      if (prev.field === field) {
        // Same field — toggle direction
        return { field, order: prev.order === "asc" ? "desc" : "asc" }
      }
      // Different field — default to asc
      return { field, order: "asc" }
    })
    // Always reset to page 1 when sort changes
    setPageRaw(1)
  }, [])

  const toggleFieldVisibility = useCallback((field: string) => {
    setHiddenFields((prev) => {
      const next = new Set(prev)
      if (next.has(field)) {
        next.delete(field)
      } else {
        next.add(field)
      }
      return next
    })
  }, [])

  const apiParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page,
      per_page: perPage,
    }
    if (sort.field) {
      params.sort = sort.field
      params.order = sort.order
    }
    return params
  }, [page, perPage, sort])

  return {
    page,
    perPage,
    sort,
    hiddenFields,
    setPage,
    toggleSort,
    toggleFieldVisibility,
    apiParams,
  }
}
