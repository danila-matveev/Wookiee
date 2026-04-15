import { useEffect, useState } from "react"
import { matrixApi, type AuditLogEntry, type PaginatedResponse } from "@/lib/matrix-api"

export function AuditLogPage() {
  const [data, setData] = useState<PaginatedResponse<AuditLogEntry> | null>(null)
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState("")
  const [actionFilter, setActionFilter] = useState("")

  useEffect(() => {
    const params: Record<string, string | number> = { page, per_page: 50 }
    if (entityFilter) params.entity_type = entityFilter
    if (actionFilter) params.action = actionFilter
    matrixApi.listAuditLogs(params).then(setData)
  }, [page, entityFilter, actionFilter])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Audit Log</h1>

      <div className="flex gap-2 mb-4">
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
        <select
          className="border rounded px-2 py-1 text-sm bg-background"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
        >
          <option value="">Все действия</option>
          {["create","update","delete","bulk_update","restore"].map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-2">Время</th>
              <th className="text-left p-2">Пользователь</th>
              <th className="text-left p-2">Действие</th>
              <th className="text-left p-2">Сущность</th>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">Название</th>
              <th className="text-left p-2">Изменения</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((log) => (
              <tr key={log.id} className="border-t hover:bg-muted/30">
                <td className="p-2 font-mono text-xs">
                  {log.timestamp ? new Date(log.timestamp).toLocaleString("ru") : "—"}
                </td>
                <td className="p-2">{log.user_email ?? "—"}</td>
                <td className="p-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                    log.action === "delete" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                    log.action === "create" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  }`}>
                    {log.action}
                  </span>
                </td>
                <td className="p-2">{log.entity_type ?? "—"}</td>
                <td className="p-2 font-mono">{log.entity_id ?? "—"}</td>
                <td className="p-2">{log.entity_name ?? "—"}</td>
                <td className="p-2 max-w-xs truncate text-xs text-muted-foreground">
                  {log.changes ? JSON.stringify(log.changes) : "—"}
                </td>
              </tr>
            ))}
            {(!data || data.items.length === 0) && (
              <tr><td colSpan={7} className="p-4 text-center text-muted-foreground">Нет записей</td></tr>
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
