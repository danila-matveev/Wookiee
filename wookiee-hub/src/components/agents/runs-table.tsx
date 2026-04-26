import { RunStatusBadge } from "@/components/agents/run-status-badge"
import type { ToolRun } from "@/types/agents"

function formatStarted(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatDuration(sec?: number): string {
  if (sec === undefined) return "—"
  if (sec < 60) return `${sec} с`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m} мин ${s.toString().padStart(2, "0")} с`
}

function formatCost(cost?: number): string {
  if (cost === undefined) return "—"
  return `$${cost.toFixed(2)}`
}

export function RunsTable({ runs }: { runs: ToolRun[] }) {
  if (runs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-[10px] p-6 text-[13px] text-muted-foreground text-center">
        Нет запусков
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[13px]">
        <thead className="bg-bg-soft border-b border-border">
          <tr className="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2 font-medium">Скилл</th>
            <th className="px-4 py-2 font-medium">Запущен</th>
            <th className="px-4 py-2 font-medium">Статус</th>
            <th className="px-4 py-2 font-medium">Длительность</th>
            <th className="px-4 py-2 font-medium">Стоимость</th>
            <th className="px-4 py-2 font-medium">Источник</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              className="border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors"
            >
              <td className="px-4 py-2.5">
                <div className="font-medium text-foreground">{run.toolName}</div>
                {run.errorMessage && (
                  <div className="text-[11px] text-rose-500 dark:text-rose-400 mt-0.5 line-clamp-1">
                    {run.errorMessage}
                  </div>
                )}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground text-[12px]">
                {formatStarted(run.startedAt)}
              </td>
              <td className="px-4 py-2.5">
                <RunStatusBadge status={run.status} />
              </td>
              <td className="px-4 py-2.5 text-muted-foreground font-mono text-[12px]">
                {formatDuration(run.durationSec)}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground font-mono text-[12px]">
                {formatCost(run.costUsd)}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground text-[12px]">
                {run.triggerSource ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
