import { CheckCircle, AlertCircle, RefreshCw } from "lucide-react"

export interface UpdateBarProps {
  lastUpdate?: string                   // formatted: '27 апр 2026, 23:24'
  weeksCovered?: string                  // '20.04–26.04, пропусков нет'
  status?: "success" | "failed" | "unknown"
  onSync?: () => Promise<void> | void
  syncing?: boolean
}

export function UpdateBar({ lastUpdate, weeksCovered, status = "unknown", onSync, syncing }: UpdateBarProps) {
  const Icon  = status === "failed" ? AlertCircle : CheckCircle
  const color = status === "failed" ? "text-[color:var(--wk-red)]"
              : status === "success" ? "text-[color:var(--wk-green)]"
              : "text-muted-foreground"

  return (
    <div className="flex items-center gap-3 px-6 py-1.5 bg-muted/30 border-b border-border text-[11px]">
      <Icon className={`w-3 h-3 ${color}`} aria-hidden />
      <span className="tabular-nums text-muted-foreground">{lastUpdate ?? "—"}</span>
      {weeksCovered && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span className={color}>{weeksCovered}</span>
        </>
      )}
      {onSync && (
        <button
          type="button" onClick={() => onSync()} disabled={syncing}
          className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium transition-colors border-border text-muted-foreground hover:bg-muted hover:border-foreground/30 disabled:opacity-50"
          aria-label="Обновить данные"
        >
          <RefreshCw className={`w-3 h-3 ${syncing ? "animate-spin" : ""}`} aria-hidden />
          {syncing ? "Обновляю…" : "Обновить"}
        </button>
      )}
    </div>
  )
}
