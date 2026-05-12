import type { ReactNode } from "react"

export interface TableColumn<T> {
  key: string
  label: string
  render?: (row: T) => ReactNode
  mono?: boolean
  dim?: boolean
}

interface CatalogTableProps<T extends { id: number }> {
  columns: TableColumn<T>[]
  data: T[]
  emptyText?: string
}

export function CatalogTable<T extends { id: number }>({
  columns,
  data,
  emptyText = "Нет данных",
}: CatalogTableProps<T>) {
  return (
    <div className="bg-surface rounded-lg border border-default overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-surface-muted/80 border-b border-default">
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
            {columns.map((col) => (
              <th key={col.key} className="px-3 py-2.5 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3 py-8 text-center text-sm text-label italic"
              >
                {emptyText}
              </td>
            </tr>
          )}
          {data.map((row) => (
            <tr
              key={row.id}
              className="group border-b border-subtle last:border-0 hover:bg-surface-muted/60 transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2.5 ${col.mono ? "font-mono text-xs" : ""} ${
                    col.dim ? "text-muted" : "text-primary"
                  }`}
                >
                  {col.render
                    ? col.render(row)
                    : String((row as Record<string, unknown>)[col.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
