import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { PriorityDot } from "@/components/shared/priority-dot"
import { StatusPill } from "@/components/shared/status-pill"
import type { KanbanCard, KanbanColumn } from "@/types/kanban"

interface DrawerHeaderProps {
  card: KanbanCard
  column: KanbanColumn | undefined
  onClose: () => void
}

export function DrawerHeader({ card, column, onClose }: DrawerHeaderProps) {
  return (
    <div className="h-14 border-b border-border bg-card flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-2.5">
        <PriorityDot priority={card.priority} size={8} />
        {column && <StatusPill label={column.title} color={column.color} />}
      </div>

      <button
        type="button"
        onClick={onClose}
        className={cn(
          "text-text-dim hover:text-foreground p-1.5 rounded",
          "hover:bg-bg-hover transition-colors"
        )}
      >
        <X size={18} />
      </button>
    </div>
  )
}
