import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ColumnVisibilityPopover } from "@/components/matrix/column-visibility-popover"

interface MatrixTopbarProps {
  fieldDefs?: Array<{ key?: string; field_name?: string; label?: string; display_name?: string; section?: string }>
  hiddenFields?: Set<string>
  onToggleField?: (fieldName: string) => void
  onCreateClick?: () => void
}

export function MatrixTopbar({
  fieldDefs,
  hiddenFields,
  onToggleField,
  onCreateClick,
}: MatrixTopbarProps) {
  return (
    <div className="flex h-10 items-center gap-2 border-b border-border px-4">
      {onCreateClick && (
        <Button
          variant="default"
          size="sm"
          onClick={onCreateClick}
          className="h-7 gap-1.5 text-xs"
        >
          <Plus className="h-3.5 w-3.5" />
          Создать
        </Button>
      )}
      {fieldDefs && hiddenFields && onToggleField && (
        <ColumnVisibilityPopover
          fields={fieldDefs}
          hiddenFields={hiddenFields}
          onToggle={onToggleField}
        />
      )}
    </div>
  )
}
