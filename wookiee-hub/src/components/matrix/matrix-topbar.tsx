import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ColumnVisibilityPopover } from "@/components/matrix/column-visibility-popover"
import { FilterChip } from "@/components/matrix/filter-chip"
import { FilterPopover, type FilterableDef } from "@/components/matrix/filter-popover"
import type { FilterEntry } from "@/stores/matrix-store"

interface MatrixTopbarProps {
  fieldDefs?: Array<{ key?: string; field_name?: string; label?: string; display_name?: string; section?: string }>
  hiddenFields?: Set<string>
  onToggleField?: (fieldName: string) => void
  onCreateClick?: () => void
  // Filter props
  activeFilters?: FilterEntry[]
  onAddFilter?: (entry: FilterEntry) => void
  onRemoveFilter?: (field: string) => void
  filterableDefs?: FilterableDef[]
  /** Optional extra action buttons rendered between filter chips and spacer */
  extraActions?: React.ReactNode
}

export function MatrixTopbar({
  fieldDefs,
  hiddenFields,
  onToggleField,
  onCreateClick,
  activeFilters,
  onAddFilter,
  onRemoveFilter,
  filterableDefs,
  extraActions,
}: MatrixTopbarProps) {
  return (
    <div className="flex min-h-10 flex-wrap items-center gap-2 border-b border-border px-4 py-1.5">
      {/* Left: Создать button */}
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

      {/* +Фильтр button */}
      {filterableDefs && onAddFilter && (
        <FilterPopover filterableDefs={filterableDefs} onAddFilter={onAddFilter} />
      )}

      {/* Active filter chips */}
      {activeFilters && activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {activeFilters.map((f) => (
            <FilterChip
              key={f.field}
              label={f.label}
              values={f.valueLabels}
              onRemove={() => onRemoveFilter?.(f.field)}
            />
          ))}
        </div>
      )}

      {/* Extra action buttons (e.g. save/load view) */}
      {extraActions}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right: Поля button */}
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
