import { X, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useMatrixStore } from "@/stores/matrix-store"
import type { MatrixEntity } from "@/stores/matrix-store"

export interface RelatedCount {
  label: string
  count: number
  entityType: string
}

interface PanelHeaderProps {
  title: string
  onClose: () => void
  isEditing: boolean
  onToggleEdit: () => void
  relatedCounts?: RelatedCount[]
  className?: string
}

export function PanelHeader({
  title,
  onClose,
  isEditing,
  onToggleEdit,
  relatedCounts = [],
  className,
}: PanelHeaderProps) {
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)
  const closeDetailPanel = useMatrixStore((s) => s.closeDetailPanel)

  const visibleCounts = relatedCounts.filter((r) => r.count > 0)

  return (
    <div
      data-slot="panel-header"
      className={cn(
        "border-b border-border px-4 py-3 shrink-0",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0 mr-2">
          <h2 className="text-base font-semibold truncate">{title}</h2>
          {isEditing && (
            <span className="text-xs text-muted-foreground shrink-0 italic">
              Редактирование...
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {/* Hide "Редактировать" button while editing — Save/Cancel in bottom bar */}
          {!isEditing && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-xs h-7 px-2"
              onClick={onToggleEdit}
            >
              <Pencil className="h-3.5 w-3.5" />
              Редактировать
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={onClose}
            aria-label="Закрыть панель"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Related entity badge counters */}
      {visibleCounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {visibleCounts.map((rel) => (
            <Badge
              key={rel.entityType}
              variant="secondary"
              className="cursor-pointer hover:bg-secondary/80 transition-colors"
              onClick={() => {
                setActiveEntity(rel.entityType as MatrixEntity)
                closeDetailPanel()
              }}
            >
              {rel.label}: {rel.count}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
