import type { RefObject } from "react"
import { CalendarDays } from "lucide-react"
import { cn } from "@/lib/utils"
import { PriorityDot } from "@/components/shared/priority-dot"
import { useKanbanStore } from "@/stores/kanban"
import type { KanbanCard } from "@/types/kanban"

interface KanbanCardComponentProps {
  card: KanbanCard
  columnColor: string
  wasDragged?: RefObject<boolean>
}

export function KanbanCardComponent({
  card,
  columnColor: _columnColor,
  wasDragged,
}: KanbanCardComponentProps) {
  const fieldEntries = Object.entries(card.fields)
  const firstField = fieldEntries.length > 0 ? fieldEntries[0] : null
  const bitrixCount = card.bitrixTasks?.length ?? 0

  return (
    <div
      className={cn(
        "bg-card border border-border rounded-lg p-3 cursor-pointer transition-all duration-150",
        "hover:border-accent-border hover:shadow-glow",
      )}
      onClick={() => {
        if (wasDragged?.current) return
        useKanbanStore.getState().openCard(card)
      }}
    >
      {/* Row 1: Title + Priority */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[13px] font-semibold truncate">{card.title}</span>
        <PriorityDot priority={card.priority} className="mt-1" />
      </div>

      {/* Row 2: Assignee */}
      {card.assignee && (
        <p className="text-[12px] text-muted-foreground mt-1">
          {card.assignee}
        </p>
      )}

      {/* Row 3: First field + Date */}
      {(firstField || card.dueDate) && (
        <div className="flex items-center justify-between gap-2 mt-2">
          {firstField && (
            <span className="text-[11px] text-text-dim truncate">
              {firstField[1]}
            </span>
          )}
          {card.dueDate && (
            <span className="flex items-center gap-1 text-[11px] text-text-dim flex-shrink-0">
              <CalendarDays size={12} />
              {card.dueDate}
            </span>
          )}
        </div>
      )}

      {/* Row 4: Tags */}
      {card.tags && card.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {card.tags.map((tag) => (
            <span
              key={tag}
              className="bg-accent-soft text-accent text-[10px] font-semibold px-1.5 py-0 rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Row 5: Bitrix tasks count */}
      {bitrixCount > 0 && (
        <p className="text-[11px] text-wk-bitrix mt-2">
          &#9889; {bitrixCount} {bitrixCount === 1 ? "задача" : bitrixCount < 5 ? "задачи" : "задач"} в Б24
        </p>
      )}
    </div>
  )
}
