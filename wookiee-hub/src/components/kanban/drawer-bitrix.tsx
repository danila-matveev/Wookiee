import { CheckCircle2, ExternalLink, Link, Plus, Zap } from "lucide-react"
import { cn } from "@/lib/utils"
import { StatusPill } from "@/components/shared/status-pill"
import type { BitrixTask } from "@/types/kanban"

interface DrawerBitrixProps {
  tasks: BitrixTask[]
}

function TaskRow({ task }: { task: BitrixTask }) {
  if (task.status === "done") {
    return (
      <div className="flex items-center gap-2.5">
        <CheckCircle2 size={14} className="text-wk-green shrink-0" />
        <span className="text-[13px] line-through opacity-60 flex-1 min-w-0 truncate">
          {task.title}
        </span>
        <StatusPill label="Готово" color="var(--color-wk-green)" />
      </div>
    )
  }

  const isInProgress = task.status === "in_progress"

  return (
    <div className="flex items-center gap-2.5">
      <div
        className={cn(
          "w-3.5 h-3.5 rounded-full border-2 shrink-0",
          isInProgress ? "border-wk-bitrix" : "border-text-dim"
        )}
      />
      <span className="text-[13px] flex-1 min-w-0 truncate">{task.title}</span>
      <span className="text-[11px] text-text-dim font-mono shrink-0">{task.id}</span>
      <span className="text-[11px] text-text-dim shrink-0">{task.assignee}</span>
      {isInProgress ? (
        <StatusPill label="В работе" color="var(--color-wk-bitrix)" />
      ) : (
        <StatusPill label="Ожидает" color="var(--color-wk-yellow)" />
      )}
    </div>
  )
}

export function DrawerBitrix({ tasks }: DrawerBitrixProps) {
  const activeTasks = tasks.filter((t) => t.status !== "done")
  const doneTasks = tasks.filter((t) => t.status === "done")
  const sorted = [...activeTasks, ...doneTasks]

  return (
    <div className="bg-card border border-wk-bitrix/30 rounded-[10px] p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-wk-bitrix/20 flex items-center justify-center">
            <Zap size={13} className="text-wk-bitrix" />
          </div>
          <span className="text-[13px] font-semibold">Битрикс24</span>
          <span className="text-[11px] text-text-dim">{tasks.length}</span>
        </div>
        <button
          type="button"
          className="flex items-center gap-1 text-[12px] text-wk-bitrix hover:opacity-80 transition-opacity"
        >
          Открыть в Б24
          <ExternalLink size={12} />
        </button>
      </div>

      {/* Content */}
      {tasks.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-4">
          <span className="text-[12px] text-muted-foreground">Нет связанных задач</span>
          <button
            type="button"
            className={cn(
              "border border-dashed border-wk-bitrix/30 rounded-lg px-3 py-1.5",
              "flex items-center gap-1.5 text-[12px] text-wk-bitrix",
              "hover:border-wk-bitrix hover:opacity-80 transition-colors cursor-pointer"
            )}
          >
            <Link size={12} />
            Привязать задачу
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {sorted.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}

          {/* Add task button */}
          <button
            type="button"
            className={cn(
              "w-full border border-dashed border-wk-bitrix/30 rounded-lg p-2",
              "flex items-center justify-center gap-1.5",
              "text-[12px] text-wk-bitrix",
              "hover:border-wk-bitrix hover:opacity-80",
              "transition-colors cursor-pointer mt-1"
            )}
          >
            <Plus size={12} />
            Привязать задачу
          </button>
        </div>
      )}
    </div>
  )
}
