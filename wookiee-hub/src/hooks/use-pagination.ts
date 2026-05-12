// usePagination — simple client-side paginator for catalog tables (W8.2).
//
// Returns `paginate(rows)` → { slice, page, totalPages, total, pageSize }.
// Page is clamped to [1, totalPages] internally so changes to filters/sort
// shrinking the dataset never leave the user stranded on an out-of-range page.

import { useCallback, useState } from "react"

export interface PaginationState {
  page: number
  pageSize: number
}

export interface PaginationResult<T> {
  slice: T[]
  page: number
  totalPages: number
  total: number
  pageSize: number
}

export function usePagination(initialPageSize = 50) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)

  const paginate = useCallback(
    <T,>(rows: T[]): PaginationResult<T> => {
      const total = rows.length
      const totalPages = Math.max(1, Math.ceil(total / pageSize))
      const safePage = Math.min(Math.max(1, page), totalPages)
      const start = (safePage - 1) * pageSize
      const end = start + pageSize
      return {
        slice: rows.slice(start, end),
        page: safePage,
        totalPages,
        total,
        pageSize,
      }
    },
    [page, pageSize],
  )

  const resetPage = useCallback(() => setPage(1), [])

  return { page, setPage, pageSize, setPageSize, paginate, resetPage }
}
