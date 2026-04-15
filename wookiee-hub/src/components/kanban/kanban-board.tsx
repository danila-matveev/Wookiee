import { useState, useEffect } from "react"
import { LayoutGrid, Table2, List } from "lucide-react"
import { boardConfigs } from "@/config/boards"
import { ViewSwitcher } from "@/components/shared/view-switcher"
import { KanbanView } from "./kanban-view"
import { TableView } from "./table-view"
import { ListView } from "./list-view"
import { CardDrawer } from "./card-drawer"
import { useKanbanStore } from "@/stores/kanban"

const viewOptions = [
  { id: "kanban", label: "Канбан", icon: LayoutGrid },
  { id: "table", label: "Таблица", icon: Table2 },
  { id: "list", label: "Список", icon: List },
]

interface KanbanBoardProps {
  boardId: string
}

export function KanbanBoard({ boardId }: KanbanBoardProps) {
  const config = boardConfigs[boardId]
  const isMobile = typeof window !== "undefined" && window.innerWidth < 1024
  const [viewMode, setViewMode] = useState<string>(isMobile ? "list" : (config?.defaultView || "kanban"))
  const { selectedCard, closeCard, initBoard, boardCards } = useKanbanStore()

  useEffect(() => {
    initBoard(boardId)
  }, [boardId, initBoard])

  const cards = boardCards[boardId] || []

  if (!config) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">{config.title}</h1>
        <div className="hidden sm:flex">
          <ViewSwitcher
            options={viewOptions}
            value={viewMode}
            onChange={setViewMode}
          />
        </div>
      </div>

      {viewMode === "kanban" && (
        <KanbanView columns={config.columns} cards={cards} boardId={boardId} />
      )}
      {viewMode === "table" && (
        <TableView columns={config.columns} cards={cards} />
      )}
      {viewMode === "list" && (
        <ListView columns={config.columns} cards={cards} />
      )}

      {selectedCard && (
        <CardDrawer
          card={selectedCard}
          columns={config.columns}
          onClose={closeCard}
        />
      )}
    </div>
  )
}
