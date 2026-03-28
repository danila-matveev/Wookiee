import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useMatrixStore } from "@/stores/matrix-store"
import { matrixApi } from "@/lib/matrix-api"
import { getBackendType } from "@/lib/entity-registry"

export function MassEditBar() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const clearSelection = useMatrixStore((s) => s.clearSelection)
  const activeEntity = useMatrixStore((s) => s.activeEntity)

  if (selectedRows.size === 0) return null

  const handleBulkUpdate = async (changes: Record<string, unknown>) => {
    const entityType = getBackendType(activeEntity)
    await matrixApi.bulkAction(entityType, {
      ids: Array.from(selectedRows),
      action: "update",
      changes,
    })
    clearSelection()
  }

  return (
    <div className="sticky bottom-0 flex items-center gap-3 border-t bg-background px-4 py-2 text-sm">
      <span className="font-medium">{selectedRows.size} выбрано</span>
      <Button variant="outline" size="sm" onClick={() => handleBulkUpdate({ status_id: 1 })}>
        Статус: Активный
      </Button>
      <Button variant="outline" size="sm" onClick={() => handleBulkUpdate({ status_id: 3 })}>
        Статус: Архив
      </Button>
      <div className="flex-1" />
      <Button variant="ghost" size="sm" onClick={clearSelection}>
        <X className="mr-1 h-3 w-3" /> Снять выделение
      </Button>
    </div>
  )
}
