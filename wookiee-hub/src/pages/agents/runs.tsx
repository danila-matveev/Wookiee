import { useEffect } from "react"
import { Loader2, AlertCircle } from "lucide-react"
import { RunsTable } from "@/components/agents/runs-table"
import { useAgentsStore } from "@/stores/agents"

export function RunsPage() {
  const { runs, loading, error, loadRuns } = useAgentsStore()

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  return (
    <div className="space-y-3">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-[18px] font-semibold text-foreground">История запусков</h1>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Хронология запусков скиллов. В Phase 1 показываются мок-данные.
          </p>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Всего: {runs.length}
        </span>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-[13px]">Загрузка запусков...</span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 gap-2 text-destructive">
          <AlertCircle size={16} />
          <span className="text-[13px]">{error}</span>
        </div>
      ) : (
        <RunsTable runs={runs} />
      )}
    </div>
  )
}
