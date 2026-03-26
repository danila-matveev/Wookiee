export type CellType = "text" | "number" | "select" | "relation" | "readonly"

interface TableCellProps {
  value: string | number | null
  type?: CellType
}

/**
 * Pure read-only table cell renderer.
 * All editing happens in the Detail Panel (Phase 2 decision).
 */
export function TableCell({ value }: TableCellProps) {
  return (
    <span className="block truncate px-2 py-1 text-sm">
      {value ?? "\u2014"}
    </span>
  )
}
