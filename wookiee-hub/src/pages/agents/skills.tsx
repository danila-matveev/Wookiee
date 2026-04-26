import { useEffect } from "react"
import { Loader2, AlertCircle } from "lucide-react"
import { ToolsTable } from "@/components/agents/tools-table"
import { useAgentsStore } from "@/stores/agents"

export function SkillsPage() {
  const { tools, loading, error, loadTools } = useAgentsStore()

  useEffect(() => {
    loadTools()
  }, [loadTools])

  return (
    <div className="space-y-3">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-[18px] font-semibold text-foreground">Табло скиллов</h1>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Каталог автоматизаций Wookiee. В Phase 1 данные показываются из локального мока.
          </p>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Всего: {tools.length}
        </span>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-[13px]">Загрузка скиллов...</span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 gap-2 text-destructive">
          <AlertCircle size={16} />
          <span className="text-[13px]">{error}</span>
        </div>
      ) : (
        <ToolsTable tools={tools} />
      )}
    </div>
  )
}
