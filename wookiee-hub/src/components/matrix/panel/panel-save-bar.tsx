import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface PanelSaveBarProps {
  onSave: () => void
  onCancel: () => void
  saving: boolean
  hasChanges: boolean
  className?: string
}

export function PanelSaveBar({
  onSave,
  onCancel,
  saving,
  hasChanges,
  className,
}: PanelSaveBarProps) {
  return (
    <div
      data-slot="panel-save-bar"
      className={cn(
        "sticky bottom-0 z-10 flex justify-end gap-2 border-t border-border bg-background px-3 py-3 shrink-0",
        className,
      )}
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onCancel}
        disabled={saving}
        className="h-8 text-xs"
      >
        Отменить
      </Button>
      <Button
        variant="default"
        size="sm"
        onClick={onSave}
        disabled={saving || !hasChanges}
        className="h-8 text-xs gap-1.5"
      >
        {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        Сохранить
      </Button>
    </div>
  )
}
