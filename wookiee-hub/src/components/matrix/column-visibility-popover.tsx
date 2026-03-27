import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Settings2 } from "lucide-react"

interface FieldLike {
  key?: string
  field_name?: string
  label?: string
  display_name?: string
  section?: string
}

interface ColumnVisibilityPopoverProps {
  fields: FieldLike[]
  hiddenFields: Set<string>
  onToggle: (fieldName: string) => void
}

export function ColumnVisibilityPopover({
  fields,
  hiddenFields,
  onToggle,
}: ColumnVisibilityPopoverProps) {
  // Group fields by section
  const groups = new Map<string, FieldLike[]>()
  for (const f of fields) {
    const section = f.section ?? "Прочие"
    if (!groups.has(section)) groups.set(section, [])
    groups.get(section)!.push(f)
  }

  return (
    <Popover>
      <PopoverTrigger className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
        <Settings2 className="h-4 w-4" />
        <span className="text-xs">Поля</span>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56 p-2">
        <p className="mb-2 px-1 text-xs font-medium text-muted-foreground">
          Видимость колонок
        </p>
        <div className="max-h-72 space-y-2 overflow-y-auto">
          {[...groups.entries()].map(([section, sectionFields]) => (
            <div key={section}>
              <p className="px-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {section}
              </p>
              {sectionFields.map((f) => {
                const fieldName = f.key ?? f.field_name ?? ""
                const displayName = f.label ?? f.display_name ?? fieldName
                return (
                  <label
                    key={fieldName}
                    className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-accent/30"
                  >
                    <Checkbox
                      checked={!hiddenFields.has(fieldName)}
                      onCheckedChange={() => onToggle(fieldName)}
                    />
                    <span className="text-xs">{displayName}</span>
                  </label>
                )
              })}
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
