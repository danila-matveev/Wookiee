import { CheckCircle2, Circle } from "lucide-react"
import { cn } from "@/lib/utils"
import { ProgressBar } from "@/components/shared/progress-bar"
import type { Stage } from "@/types/kanban"

interface DrawerStagesProps {
  stages: Stage[]
}

export function DrawerStages({ stages }: DrawerStagesProps) {
  const doneCount = stages.filter((s) => s.done).length
  const percent = stages.length > 0 ? Math.round((doneCount / stages.length) * 100) : 0

  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[13px] font-bold">Этапы</span>
        <span className="text-[13px] text-muted-foreground">{percent}%</span>
      </div>

      <ProgressBar value={percent} />

      {/* Stage list */}
      <div className="flex flex-col gap-3 mt-3">
        {stages.map((stage) => (
          <div key={stage.name} className="flex items-center gap-2.5">
            {stage.done ? (
              <>
                <CheckCircle2 size={16} className="text-wk-green shrink-0" />
                <span className="text-[13px] line-through text-muted-foreground">
                  {stage.name}
                </span>
              </>
            ) : stage.active ? (
              <>
                <div
                  className={cn(
                    "w-4 h-4 rounded-full border-2 border-accent bg-accent-soft",
                    "flex items-center justify-center shrink-0"
                  )}
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                </div>
                <span className="text-[13px] font-semibold">{stage.name}</span>
                <span className="text-[9px] bg-accent-soft text-accent rounded px-1.5 py-0.5 font-semibold">
                  Текущий
                </span>
              </>
            ) : (
              <>
                <Circle size={16} className="text-text-dim shrink-0" />
                <span className="text-[13px] text-text-dim">{stage.name}</span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
