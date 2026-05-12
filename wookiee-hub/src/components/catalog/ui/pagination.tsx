import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react"

interface Props {
  page: number
  totalPages: number
  total: number
  pageSize: number
  onPage: (p: number) => void
  onPageSize?: (s: number) => void
  pageSizeOptions?: number[]
}

/**
 * Pagination footer for catalog tables (W8.2).  Renders nothing when
 * `total === 0`.  Page-size selector is optional — pass `onPageSize` to
 * enable.  Default options are 25/50/100/200.
 */
export function Pagination({
  page, totalPages, total, pageSize, onPage, onPageSize, pageSizeOptions,
}: Props) {
  if (total === 0) return null
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  const sizes = pageSizeOptions ?? [25, 50, 100, 200]
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 border-t border-stone-100 text-xs text-stone-600">
      <div>Показаны {start}–{end} из {total}</div>
      <div className="flex items-center gap-2">
        {onPageSize && (
          <select
            className="border border-stone-200 rounded px-1.5 py-0.5 bg-white"
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value))}
          >
            {sizes.map((s) => <option key={s} value={s}>{s} / страница</option>)}
          </select>
        )}
        <button
          disabled={page <= 1}
          onClick={() => onPage(1)}
          className="p-1 hover:bg-stone-100 rounded disabled:opacity-30"
          aria-label="Первая страница"
        >
          <ChevronsLeft className="w-3.5 h-3.5" />
        </button>
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="p-1 hover:bg-stone-100 rounded disabled:opacity-30"
          aria-label="Предыдущая страница"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
        <span>{page} / {totalPages}</span>
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="p-1 hover:bg-stone-100 rounded disabled:opacity-30"
          aria-label="Следующая страница"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(totalPages)}
          className="p-1 hover:bg-stone-100 rounded disabled:opacity-30"
          aria-label="Последняя страница"
        >
          <ChevronsRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
