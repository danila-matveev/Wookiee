import { cn } from "@/lib/utils"
import { RunStatusBadge } from "@/components/agents/run-status-badge"
import type { Tool } from "@/types/agents"

const statusLabels: Record<Tool["status"], string> = {
  active: "Активен",
  paused: "На паузе",
  deprecated: "Устарел",
}

const statusTones: Record<Tool["status"], string> = {
  active: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  paused: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  deprecated: "bg-muted text-muted-foreground border-border",
}

function formatDate(iso?: string): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function ToolsTable({ tools }: { tools: Tool[] }) {
  if (tools.length === 0) {
    return (
      <div className="bg-card border border-border rounded-[10px] p-6 text-[13px] text-muted-foreground text-center">
        Нет скиллов
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[13px]">
        <thead className="bg-bg-soft border-b border-border">
          <tr className="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2 font-medium">Скилл</th>
            <th className="px-4 py-2 font-medium">Категория</th>
            <th className="px-4 py-2 font-medium">Версия</th>
            <th className="px-4 py-2 font-medium">Статус</th>
            <th className="px-4 py-2 font-medium">Последний запуск</th>
            <th className="px-4 py-2 font-medium">Результат</th>
          </tr>
        </thead>
        <tbody>
          {tools.map((tool) => (
            <tr
              key={tool.id}
              className="border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors"
            >
              <td className="px-4 py-2.5">
                <div className="font-medium text-foreground">{tool.name}</div>
                {tool.description && (
                  <div className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                    {tool.description}
                  </div>
                )}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">{tool.category}</td>
              <td className="px-4 py-2.5 text-muted-foreground font-mono text-[12px]">
                {tool.version}
              </td>
              <td className="px-4 py-2.5">
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium",
                    statusTones[tool.status]
                  )}
                >
                  {statusLabels[tool.status]}
                </span>
              </td>
              <td className="px-4 py-2.5 text-muted-foreground text-[12px]">
                {formatDate(tool.lastRunAt)}
              </td>
              <td className="px-4 py-2.5">
                {tool.lastStatus ? <RunStatusBadge status={tool.lastStatus} /> : <span className="text-muted-foreground">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
