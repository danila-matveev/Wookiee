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
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-stone-50/80 border-b border-stone-200">
          <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
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
                className="px-3 py-8 text-center text-sm text-stone-400 italic"
              >
                {emptyText}
              </td>
            </tr>
          )}
          {data.map((row) => (
            <tr
              key={row.id}
              className="group border-b border-stone-100 last:border-0 hover:bg-stone-50/60 transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2.5 ${col.mono ? "font-mono text-xs" : ""} ${
                    col.dim ? "text-stone-500" : "text-stone-900"
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
