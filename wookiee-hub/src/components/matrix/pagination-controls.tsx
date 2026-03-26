import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react"

interface PaginationControlsProps {
  page: number
  pages: number
  total: number
  perPage: number
  onPageChange: (page: number) => void
}

/**
 * Builds a window of page numbers with ellipsis when there are many pages.
 * Always shows first, last, and up to 5 pages around current.
 */
function getPageNumbers(current: number, total: number): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const pages: (number | "...")[] = []
  const left = Math.max(2, current - 1)
  const right = Math.min(total - 1, current + 1)

  pages.push(1)
  if (left > 2) pages.push("...")
  for (let i = left; i <= right; i++) pages.push(i)
  if (right < total - 1) pages.push("...")
  pages.push(total)

  return pages
}

export function PaginationControls({
  page,
  pages,
  total,
  perPage,
  onPageChange,
}: PaginationControlsProps) {
  if (pages <= 1) return null

  const from = (page - 1) * perPage + 1
  const to = Math.min(page * perPage, total)
  const pageNumbers = getPageNumbers(page, pages)

  return (
    <div className="flex items-center justify-between px-2 py-2 text-sm text-muted-foreground">
      <span className="text-xs">
        Показано {from}–{to} из {total}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          className="h-7 w-7"
          disabled={page <= 1}
          onClick={() => onPageChange(1)}
        >
          <ChevronsLeft className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="h-7 w-7"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>

        {pageNumbers.map((p, idx) =>
          p === "..." ? (
            <span key={`ellipsis-${idx}`} className="px-1 text-xs">
              ...
            </span>
          ) : (
            <Button
              key={p}
              variant={p === page ? "outline" : "ghost"}
              size="icon-sm"
              className="h-7 w-7 text-xs"
              onClick={() => onPageChange(p)}
            >
              {p}
            </Button>
          ),
        )}

        <Button
          variant="ghost"
          size="icon-sm"
          className="h-7 w-7"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="h-7 w-7"
          disabled={page >= pages}
          onClick={() => onPageChange(pages)}
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
