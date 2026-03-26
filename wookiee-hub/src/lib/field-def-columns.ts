import type { FieldDefinition } from "@/lib/matrix-api"
import type { Column } from "@/components/matrix/data-table"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"

// ── Types ────────────────────────────────────────────────────────────────────

/**
 * Extended Column type that carries the original FieldDefinition.
 * DataTable can use `fieldDef` for sort logic and type detection.
 */
export interface FieldDefColumn<T> extends Column<T> {
  fieldDef: FieldDefinition
}

// ── Converter ────────────────────────────────────────────────────────────────

/**
 * Convert FieldDefinition[] into Column[] for DataTable consumption.
 *
 * - Filters by `is_visible` and excludes fields in `hiddenFields`
 * - Sorts by `sort_order`
 * - For `_id` reference fields: maps column key to `_name` suffix
 *   (e.g. `kategoriya_id` -> `kategoriya_name`) so it reads pre-joined backend data
 * - Carries original FieldDefinition on each column for sort/type logic
 */
export function fieldDefsToColumns<T>(
  defs: FieldDefinition[],
  _lookupCache: Record<string, unknown[]>,
  hiddenFields: Set<string>,
): FieldDefColumn<T>[] {
  return defs
    .filter((d) => d.is_visible && !hiddenFields.has(d.field_name))
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((def) => {
      const isReferenceField = def.field_name in LOOKUP_TABLE_MAP
      // For _id fields, read from the pre-joined _name column
      const columnKey = isReferenceField
        ? def.field_name.replace(/_id$/, "_name")
        : def.field_name

      return {
        key: columnKey,
        label: def.display_name,
        fieldDef: def,
      }
    })
}
