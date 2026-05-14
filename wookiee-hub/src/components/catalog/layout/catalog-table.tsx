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
  /**
   * W10.14 — клик по строке открывает ReferenceDrawer на reference-страницах.
   * Не вызывается при клике на интерактивные элементы внутри ячеек (button/a/input/select).
   */
  onRowClick?: (row: T) => void
}

export function CatalogTable<T extends { id: number }>({
  columns,
  data,
  emptyText = "Нет данных",
  onRowClick,
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
              onClick={
                onRowClick
                  ? (e) => {
                      // Игнорируем клики по интерактивным элементам внутри ячеек
                      // (RowActions, ссылки, кнопки), чтобы не открывать drawer
                      // одновременно с действием.
                      const target = e.target as HTMLElement
                      if (target.closest("button, a, input, select, textarea, [data-no-row-click]")) {
                        return
                      }
                      onRowClick(row)
                    }
                  : undefined
              }
              className={`group border-b border-stone-100 last:border-0 hover:bg-stone-50/60 transition-colors ${
                onRowClick ? "cursor-pointer" : ""
              }`}
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
