import { useEffect, useState } from "react"
import { matrixApi, type ArchiveRecord, type PaginatedResponse } from "@/lib/matrix-api"

export function ArchiveManagerPage() {
  const [data, setData] = useState<PaginatedResponse<ArchiveRecord> | null>(null)
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState("")

  const load = () => {
    const params: Record<string, string | number> = { page, per_page: 50 }
    if (entityFilter) params.entity_type = entityFilter
    matrixApi.listArchive(params).then(setData)
  }

  useEffect(load, [page, entityFilter])

  const handleRestore = async (id: number) => {
    await matrixApi.restoreArchive(id)
    load()
  }

  const handleHardDelete = async (id: number) => {
    if (!confirm("Удалить навсегда? Это действие необратимо.")) return
    await matrixApi.hardDeleteArchive(id)
    load()
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Архив</h1>

      <div className="mb-4">
        <select
          className="border rounded px-2 py-1 text-sm bg-background"
          value={entityFilter}
          onChange={(e) => { setEntityFilter(e.target.value); setPage(1) }}
        >
          <option value="">Все сущности</option>
          {["modeli_osnova","modeli","artikuly","tovary","cveta","fabriki","importery"].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-2">Таблица</th>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">Удалено</th>
              <th className="text-left p-2">Кем</th>
              <th className="text-left p-2">Истекает</th>
              <th className="text-left p-2">Связанных</th>
              <th className="text-left p-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((rec) => (
              <tr key={rec.id} className="border-t hover:bg-muted/30">
                <td className="p-2 font-medium">{rec.original_table}</td>
                <td className="p-2 font-mono">{rec.original_id}</td>
                <td className="p-2 text-xs">
                  {rec.deleted_at ? new Date(rec.deleted_at).toLocaleString("ru") : "—"}
                </td>
                <td className="p-2">{rec.deleted_by ?? "—"}</td>
                <td className="p-2 text-xs">
                  {rec.expires_at ? new Date(rec.expires_at).toLocaleDateString("ru") : "—"}
                </td>
                <td className="p-2 text-center">{rec.related_records?.length ?? 0}</td>
                <td className="p-2">
                  <div className="flex gap-1">
                    {rec.restore_available && (
                      <button
                        className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400"
                        onClick={() => handleRestore(rec.id)}
                      >
                        Восстановить
                      </button>
                    )}
                    <button
                      className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400"
                      onClick={() => handleHardDelete(rec.id)}
                    >
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(!data || data.items.length === 0) && (
              <tr><td colSpan={7} className="p-4 text-center text-muted-foreground">Архив пуст</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.pages > 1 && (
        <div className="flex gap-2 mt-3 justify-center">
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            ← Назад
          </button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            {page} / {data.pages}
          </span>
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page >= data.pages}
            onClick={() => setPage(p => p + 1)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  )
}
