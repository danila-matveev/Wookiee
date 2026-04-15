import type { KanbanColumn, KanbanCard } from "@/types/kanban"
import { StatusPill } from "@/components/shared/status-pill"
import { PriorityDot } from "@/components/shared/priority-dot"
import { useKanbanStore } from "@/stores/kanban"

interface ListViewProps {
  columns: KanbanColumn[]
  cards: KanbanCard[]
}

export function ListView({ columns, cards }: ListViewProps) {
  function getColumn(card: KanbanCard): KanbanColumn | undefined {
    return columns.find((col) => col.id === card.column)
  }

  return (
    <div className="flex flex-col">
      {cards.map((card) => {
        const column = getColumn(card)

        return (
          <div
            key={card.id}
            className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-bg-hover transition-colors cursor-pointer"
            onClick={() => useKanbanStore.getState().openCard(card)}
          >
            <PriorityDot priority={card.priority} size={8} />

            <span className="text-[13px] font-semibold flex-1 truncate">
              {card.title}
            </span>

            {card.assignee && (
              <span className="text-[12px] text-text-dim">
                {card.assignee}
              </span>
            )}

            {column && (
              <StatusPill label={column.title} color={column.color} />
            )}

            {card.dueDate && (
              <span className="text-[12px] text-text-dim">{card.dueDate}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
