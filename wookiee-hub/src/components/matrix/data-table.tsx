import { Fragment } from "react"
import { ChevronRight, ChevronDown, ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { TableCell, type CellType } from "./table-cell"
import { cn } from "@/lib/utils"
import type { TableSortState } from "@/hooks/use-table-state"
import type { FieldDefColumn } from "@/lib/field-def-columns"

export interface Column<T> {
  key: string
  label: string
  width?: number
  type?: CellType
  options?: { id: number; label: string }[]
  render?: (row: T) => React.ReactNode
}

interface DataTableProps<T extends { id: number }> {
  columns: (Column<T> | FieldDefColumn<T>)[]
  data: T[]
  loading?: boolean
  expandedRows?: Set<number>
  selectedRows?: Set<number>
  childrenMap?: Map<number, T[]>
  hasChildren?: (row: T) => boolean
  onToggleExpand?: (id: number) => void
  onToggleSelect?: (id: number) => void
  onRowClick?: (id: number) => void
  onSort?: (fieldName: string) => void
  sortState?: TableSortState
}

function isFieldDefColumn<T>(col: Column<T>): col is FieldDefColumn<T> {
  return "fieldDef" in col
}

/** Status badge: green for active, gray for archived */
function StatusBadge({ value }: { value: string | null }) {
  if (!value) return <span className="block truncate px-2 py-1 text-sm">{"\u2014"}</span>

  if (value === "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0439") {
    return (
      <span className="px-2 py-1">
        <Badge className="bg-green-100 text-green-800 border-green-200 hover:bg-green-100">
          {value}
        </Badge>
      </span>
    )
  }

  if (value === "\u0410\u0440\u0445\u0438\u0432") {
    return (
      <span className="px-2 py-1">
        <Badge className="bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-100">
          {value}
        </Badge>
      </span>
    )
  }

  return (
    <span className="px-2 py-1">
      <Badge variant="outline">{value}</Badge>
    </span>
  )
}

/** Sort indicator icon for column headers */
function SortIndicator({ field, sortState }: { field: string; sortState?: TableSortState }) {
  if (!sortState || sortState.field !== field) {
    return <ArrowUpDown className="ml-1 h-3 w-3 text-muted-foreground/50" />
  }
  return sortState.order === "asc"
    ? <ArrowUp className="ml-1 h-3 w-3 text-foreground" />
    : <ArrowDown className="ml-1 h-3 w-3 text-foreground" />
}

function isStatusColumn<T>(col: Column<T> | FieldDefColumn<T>): boolean {
  if (isFieldDefColumn(col) && col.fieldDef.field_name === "status_id") return true
  return col.key === "status_name"
}

export function DataTable<T extends { id: number }>({
  columns,
  data,
  loading,
  expandedRows = new Set(),
  selectedRows = new Set(),
  childrenMap,
  hasChildren,
  onToggleExpand,
  onToggleSelect,
  onRowClick,
  onSort,
  sortState,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground">
        Загрузка...
      </div>
    )
  }

  return (
    <div className="overflow-auto rounded-md border border-border">
      <table className="w-full table-fixed border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
          <tr>
            <th className="w-10 border-b border-border px-2 py-2" />
            <th className="w-8 border-b border-border px-2 py-2" />
            {columns.map((col) => {
              const hasFieldDef = isFieldDefColumn(col)
              const sortFieldName = hasFieldDef ? col.fieldDef.field_name : col.key
              const isSortable = !!(onSort && hasFieldDef)
              return (
                <th
                  key={col.key}
                  style={col.width ? { width: col.width } : undefined}
                  className={cn(
                    "border-b border-border px-2 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground",
                    isSortable && "cursor-pointer select-none",
                  )}
                  onClick={isSortable ? () => onSort(sortFieldName) : undefined}
                >
                  <span className="inline-flex items-center">
                    {col.label}
                    {isSortable && (
                      <SortIndicator field={sortFieldName} sortState={sortState} />
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const isExpanded = expandedRows.has(row.id)
            const hasKids = hasChildren?.(row) ?? false
            const children = childrenMap?.get(row.id) ?? []
            const rowRecord = row as Record<string, unknown>
            const isArchived = rowRecord.status_name === "\u0410\u0440\u0445\u0438\u0432"

            return (
              <Fragment key={row.id}>
                <tr
                  className={cn(
                    "group border-b border-border transition-colors hover:bg-accent/20",
                    selectedRows.has(row.id) && "bg-accent/10",
                    isArchived && "opacity-60",
                  )}
                >
                  <td className="px-2 py-1.5 text-center">
                    {hasKids ? (
                      <button
                        onClick={() => onToggleExpand?.(row.id)}
                        className="rounded p-0.5 hover:bg-accent/50"
                      >
                        {isExpanded
                          ? <ChevronDown className="h-4 w-4" />
                          : <ChevronRight className="h-4 w-4" />}
                      </button>
                    ) : (
                      <span className="inline-block w-5" />
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <Checkbox
                      checked={selectedRows.has(row.id)}
                      onCheckedChange={() => onToggleSelect?.(row.id)}
                    />
                  </td>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-0 py-0 cursor-pointer"
                      onClick={() => onRowClick?.(row.id)}
                    >
                      {col.render ? (
                        col.render(row)
                      ) : isStatusColumn(col) ? (
                        <StatusBadge value={rowRecord[col.key] as string | null} />
                      ) : (
                        <TableCell
                          value={rowRecord[col.key] as string | number | null}
                          type={col.type ?? "text"}
                        />
                      )}
                    </td>
                  ))}
                </tr>
                {isExpanded &&
                  children.map((child) => {
                    const childRecord = child as Record<string, unknown>
                    const isChildArchived = childRecord.status_name === "\u0410\u0440\u0445\u0438\u0432"
                    return (
                      <tr
                        key={`child-${child.id}`}
                        className={cn(
                          "border-b border-border bg-muted/20 hover:bg-accent/10",
                          isChildArchived && "opacity-60",
                        )}
                      >
                        <td />
                        <td className="px-2 py-1.5">
                          <Checkbox
                            checked={selectedRows.has(child.id)}
                            onCheckedChange={() => onToggleSelect?.(child.id)}
                          />
                        </td>
                        {columns.map((col) => (
                          <td key={col.key} className="px-0 py-0">
                            {col.render ? (
                              col.render(child)
                            ) : isStatusColumn(col) ? (
                              <StatusBadge value={childRecord[col.key] as string | null} />
                            ) : (
                              <TableCell
                                value={childRecord[col.key] as string | number | null}
                                type={col.type ?? "text"}
                              />
                            )}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
