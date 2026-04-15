import type { KanbanCard, KanbanColumn } from "@/types/kanban"
import { DrawerHeader } from "./drawer-header"
import { DrawerFields } from "./drawer-fields"
import { DrawerStages } from "./drawer-stages"
import { DrawerBitrix } from "./drawer-bitrix"
import { DrawerBlocks } from "./drawer-blocks"
import { DrawerComments } from "./drawer-comments"

interface CardDrawerProps {
  card: KanbanCard
  columns: KanbanColumn[]
  onClose: () => void
}

export function CardDrawer({ card, columns, onClose }: CardDrawerProps) {
  const column = columns.find((c) => c.id === card.column)

  return (
    <div className="fixed inset-0 z-[100]" onClick={onClose}>
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="absolute right-0 top-0 bottom-0 w-full md:w-[min(680px,90vw)] bg-card shadow-[-8px_0_30px_rgba(0,0,0,0.3)] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky header */}
        <DrawerHeader card={card} column={column} onClose={onClose} />

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {/* Read-only hint on mobile */}
          <div className="sm:hidden bg-accent-soft text-accent text-[12px] px-3 py-2 rounded-md">
            Откройте на десктопе для редактирования
          </div>

          {/* Title & Description */}
          <div>
            <h2 className="text-[22px] font-bold">{card.title}</h2>
            {card.description && (
              <p className="text-[13px] text-muted-foreground mt-2 leading-relaxed">
                {card.description}
              </p>
            )}
            {card.tags && card.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {card.tags.map((tag) => (
                  <span
                    key={tag}
                    className="bg-accent-soft text-accent text-[11px] font-semibold px-2 py-0.5 rounded"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Fields */}
          <DrawerFields card={card} column={column} />

          {/* Stages */}
          {card.stages && card.stages.length > 0 && (
            <DrawerStages stages={card.stages} />
          )}

          {/* Bitrix tasks */}
          {card.bitrixTasks && <DrawerBitrix tasks={card.bitrixTasks} />}

          {/* Content blocks */}
          {card.blocks && card.blocks.length > 0 && (
            <DrawerBlocks blocks={card.blocks} />
          )}

          {/* Comments */}
          {card.comments && card.comments.length > 0 && (
            <DrawerComments comments={card.comments} />
          )}
        </div>
      </div>
    </div>
  )
}
