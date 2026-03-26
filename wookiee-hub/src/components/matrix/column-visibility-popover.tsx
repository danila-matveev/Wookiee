import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Settings2 } from "lucide-react"
import type { FieldDefinition } from "@/lib/matrix-api"

interface ColumnVisibilityPopoverProps {
  fields: FieldDefinition[]
  hiddenFields: Set<string>
  onToggle: (fieldName: string) => void
}

export function ColumnVisibilityPopover({
  fields,
  hiddenFields,
  onToggle,
}: ColumnVisibilityPopoverProps) {
  const visibleFields = fields.filter((f) => f.is_visible)

  return (
    <Popover>
      <PopoverTrigger className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
        <Settings2 className="h-4 w-4" />
        <span className="text-xs">Настроить поля</span>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56 p-2">
        <p className="mb-2 px-1 text-xs font-medium text-muted-foreground">
          Видимость колонок
        </p>
        <div className="max-h-64 space-y-0.5 overflow-y-auto">
          {visibleFields.map((f) => (
            <label
              key={f.field_name}
              className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 hover:bg-accent/30"
            >
              <Checkbox
                checked={!hiddenFields.has(f.field_name)}
                onCheckedChange={() => onToggle(f.field_name)}
              />
              <span className="text-sm">{f.display_name}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
