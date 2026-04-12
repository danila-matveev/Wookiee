import { useState, useCallback } from "react"
import { Plus } from "lucide-react"
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from "@dnd-kit/core"
import type { DragStartEvent, DragEndEvent, DragOverEvent } from "@dnd-kit/core"
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { motion, useReducedMotion } from "motion/react"
import type { KanbanColumn, KanbanCard } from "@/types/kanban"
import { KanbanCardComponent } from "./kanban-card"
import { SortableCard } from "./sortable-card"
import { useKanbanStore } from "@/stores/kanban"
import { springSnappy } from "@/lib/motion"

interface KanbanViewProps {
  columns: KanbanColumn[]
  cards: KanbanCard[]
  boardId: string
}

function DroppableColumn({
  column,
  cards,
}: {
  column: KanbanColumn
  cards: KanbanCard[]
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id })

  return (
    <div
      key={column.id}
      className="min-w-[220px] max-w-[260px] flex-shrink-0 flex flex-col"
    >
      {/* Column header */}
      <div className="flex items-center gap-2 mb-3 px-1">
        <div
          className="rounded-full flex-shrink-0"
          style={{
            backgroundColor: column.color,
            width: 8,
            height: 8,
          }}
        />
        <span className="text-[12px] uppercase tracking-[0.04em] text-muted-foreground font-semibold">
          {column.title}
        </span>
        <span className="ml-auto text-[11px] text-text-dim">
          {cards.length}
        </span>
      </div>

      {/* Cards */}
      <motion.div
        ref={setNodeRef}
        className="flex flex-col gap-2 min-h-[40px] rounded-lg"
        animate={{
          backgroundColor: isOver ? "var(--color-accent-soft)" : "rgba(0,0,0,0)",
          scale: isOver ? 1.01 : 1,
        }}
        transition={{ duration: 0.15 }}
      >
        <SortableContext
          items={cards.map((c) => c.id)}
          strategy={verticalListSortingStrategy}
        >
          {cards.map((card) => (
            <SortableCard
              key={card.id}
              card={card}
              columnColor={column.color}
            />
          ))}
        </SortableContext>
      </motion.div>

      {/* Add button */}
      <div className="border border-dashed border-border rounded-lg p-2 flex items-center justify-center gap-1.5 text-[12px] text-text-dim hover:border-accent-border hover:text-accent transition-colors cursor-pointer mt-2">
        <Plus size={14} />
        Добавить
      </div>
    </div>
  )
}

export function KanbanView({ columns, cards, boardId }: KanbanViewProps) {
  const [activeCard, setActiveCard] = useState<KanbanCard | null>(null)
  const moveCard = useKanbanStore((s) => s.moveCard)
  const reducedMotion = useReducedMotion()

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 10,
        delay: 150,
        tolerance: 5,
      },
    })
  )

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const card = cards.find((c) => c.id === event.active.id)
      if (card) setActiveCard(card)
    },
    [cards]
  )

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const { active, over } = event
      if (!over) return

      const activeCardId = active.id as string
      const overId = over.id as string

      // Check if we're over a column directly
      const overColumn = columns.find((col) => col.id === overId)
      if (overColumn) {
        const currentCard = cards.find((c) => c.id === activeCardId)
        if (currentCard && currentCard.column !== overColumn.id) {
          moveCard(boardId, activeCardId, overColumn.id)
        }
        return
      }

      // Check if we're over another card — move to that card's column
      const overCard = cards.find((c) => c.id === overId)
      if (overCard) {
        const currentCard = cards.find((c) => c.id === activeCardId)
        if (currentCard && currentCard.column !== overCard.column) {
          moveCard(boardId, activeCardId, overCard.column)
        }
      }
    },
    [cards, columns, boardId, moveCard]
  )

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      setActiveCard(null)

      if (!over) return

      const activeCardId = active.id as string
      const overId = over.id as string

      // Check if dropped on a column
      const overColumn = columns.find((col) => col.id === overId)
      if (overColumn) {
        moveCard(boardId, activeCardId, overColumn.id)
        return
      }

      // Check if dropped on a card
      const overCard = cards.find((c) => c.id === overId)
      if (overCard) {
        moveCard(boardId, activeCardId, overCard.column)
      }
    },
    [cards, columns, boardId, moveCard]
  )

  // Find the column color for the active card's overlay
  const activeColumnColor =
    activeCard
      ? columns.find((col) => col.id === activeCard.column)?.color ?? "#888"
      : "#888"

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 overflow-x-auto pb-4">
        {columns.map((column) => {
          const columnCards = cards.filter((c) => c.column === column.id)
          return (
            <DroppableColumn
              key={column.id}
              column={column}
              cards={columnCards}
            />
          )
        })}
      </div>

      <DragOverlay>
        {activeCard ? (
          <motion.div
            initial={reducedMotion ? false : { scale: 1, rotate: 0 }}
            animate={{
              scale: 1.04,
              rotate: 2,
              boxShadow: "var(--shadow-drag)",
            }}
            transition={springSnappy}
          >
            <KanbanCardComponent
              card={activeCard}
              columnColor={activeColumnColor}
            />
          </motion.div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
