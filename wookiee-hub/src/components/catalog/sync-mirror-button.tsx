import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertCircle, CheckCircle2, ChevronDown, RefreshCw } from "lucide-react"

import {
  CATALOG_SYNC_OPTIONS,
  type CatalogSyncSheet,
  fetchCatalogSyncStatus,
  triggerCatalogSync,
} from "@/api/catalog/sync-mirror"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { formatDateTime } from "@/lib/format"

const STATUS_QUERY_KEY = ["catalog", "sync-mirror", "status"] as const

function relativeAgo(iso?: string | null): string | null {
  if (!iso) return null
  const ts = new Date(iso).getTime()
  if (Number.isNaN(ts)) return null
  const diffMs = Date.now() - ts
  if (diffMs < 0) return formatDateTime(iso)
  const min = Math.floor(diffMs / 60_000)
  if (min < 1) return "только что"
  if (min < 60) return `${min} мин назад`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} ч назад`
  return formatDateTime(iso)
}

export function SyncMirrorButton() {
  const qc = useQueryClient()
  const statusQ = useQuery({
    queryKey: STATUS_QUERY_KEY,
    queryFn: fetchCatalogSyncStatus,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3_000 : 30_000),
  })

  const [flash, setFlash] = useState<"success" | "error" | null>(null)
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    return () => {
      if (flashTimer.current) clearTimeout(flashTimer.current)
    }
  }, [])

  const triggerMut = useMutation({
    mutationFn: (sheet: CatalogSyncSheet) => triggerCatalogSync(sheet),
    onSuccess: (res) => {
      setFlash(res.status === "ok" ? "success" : "error")
      if (flashTimer.current) clearTimeout(flashTimer.current)
      flashTimer.current = setTimeout(() => setFlash(null), 4_000)
      qc.invalidateQueries({ queryKey: STATUS_QUERY_KEY })
    },
    onError: () => {
      setFlash("error")
      if (flashTimer.current) clearTimeout(flashTimer.current)
      flashTimer.current = setTimeout(() => setFlash(null), 4_000)
      qc.invalidateQueries({ queryKey: STATUS_QUERY_KEY })
    },
  })

  const live = statusQ.data
  const isRunning = triggerMut.isPending || live?.status === "running"
  const isError   = flash === "error" || (!isRunning && live?.status === "error")
  const isSuccess = flash === "success" || (!isRunning && live?.status === "success")

  const Icon = isError ? AlertCircle : isSuccess ? CheckCircle2 : RefreshCw
  const iconClass = isError
    ? "text-[color:var(--wk-red,#b45309)]"
    : isSuccess
      ? "text-[color:var(--wk-green,#059669)]"
      : "text-muted-foreground"

  const lastRun = relativeAgo(live?.finished_at ?? live?.started_at ?? null)

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button type="button" size="sm" variant="outline" />}
          disabled={isRunning}
          className="gap-1.5 h-8 px-2.5 text-xs font-medium"
          aria-label="Обновить зеркало Hub → Google Sheets"
        >
          <Icon className={`w-3.5 h-3.5 ${iconClass} ${isRunning && Icon === RefreshCw ? "animate-spin" : ""}`} aria-hidden />
          {isRunning ? "Обновляю…" : "Обновить зеркало"}
          <ChevronDown className="w-3 h-3 opacity-60" aria-hidden />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          {CATALOG_SYNC_OPTIONS.map((opt) => (
            <DropdownMenuItem
              key={opt.value}
              disabled={isRunning}
              onSelect={() => triggerMut.mutate(opt.value)}
            >
              {opt.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <span className="text-[11px] text-muted-foreground tabular-nums" title={live?.output_summary ?? undefined}>
        {isRunning
          ? "идёт синхронизация…"
          : isError
            ? (live?.error_message ?? "ошибка")
            : lastRun
              ? `последний запуск: ${lastRun}`
              : "ещё не запускали"}
      </span>
    </div>
  )
}
