import { useRef } from "react"
import { useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { motion, useReducedMotion } from "motion/react"
import { KanbanCardComponent } from "./kanban-card"
import type { KanbanCard } from "@/types/kanban"
import { springDefault } from "@/lib/motion"

interface SortableCardProps {
  card: KanbanCard
  columnColor: string
}

export function SortableCard({ card, columnColor }: SortableCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id })

  const wasDragged = useRef(false)
  const reducedMotion = useReducedMotion()

  if (isDragging) wasDragged.current = true

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <motion.div
      ref={setNodeRef}
      style={style}
      layout={!reducedMotion && !isDragging}
      transition={springDefault}
      {...attributes}
      {...listeners}
      onPointerUp={() => {
        setTimeout(() => { wasDragged.current = false }, 0)
      }}
    >
      <KanbanCardComponent card={card} columnColor={columnColor} wasDragged={wasDragged} />
    </motion.div>
  )
}
