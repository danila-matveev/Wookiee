import type { KanbanColumn, KanbanCard } from "@/types/kanban"
import { StatusPill } from "@/components/shared/status-pill"
import { PriorityDot } from "@/components/shared/priority-dot"
import { useKanbanStore } from "@/stores/kanban"

interface TableViewProps {
  columns: KanbanColumn[]
  cards: KanbanCard[]
}

export function TableView({ columns, cards }: TableViewProps) {
  function getColumn(card: KanbanCard): KanbanColumn | undefined {
    return columns.find((col) => col.id === card.column)
  }

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-4 py-3">
              Название
            </th>
            <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-4 py-3">
              Ответственный
            </th>
            <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-4 py-3">
              Статус
            </th>
            <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-4 py-3">
              Срок
            </th>
            <th className="text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-4 py-3">
              Приоритет
            </th>
          </tr>
        </thead>
        <tbody>
          {cards.map((card) => {
            const column = getColumn(card)

            return (
              <tr
                key={card.id}
                className="px-4 py-3 border-b border-border/20 hover:bg-bg-hover/50 transition-colors cursor-pointer"
                onClick={() => useKanbanStore.getState().openCard(card)}
              >
                <td className="px-4 py-3 text-[13px] font-semibold">
                  {card.title}
                </td>
                <td className="px-4 py-3 text-[12px] text-muted-foreground">
                  {card.assignee ?? "\u2014"}
                </td>
                <td className="px-4 py-3">
                  {column ? (
                    <StatusPill label={column.title} color={column.color} />
                  ) : (
                    "\u2014"
                  )}
                </td>
                <td className="px-4 py-3 text-[12px] text-text-dim">
                  {card.dueDate ?? "\u2014"}
                </td>
                <td className="px-4 py-3">
                  <PriorityDot priority={card.priority} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
