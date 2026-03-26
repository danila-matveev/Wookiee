import type { FieldDefinition, LookupItem } from "@/lib/matrix-api"
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

// ── Lookup cache type ────────────────────────────────────────────────────────

type LookupCache = Record<string, LookupItem[]>

// ── Converter ────────────────────────────────────────────────────────────────

/**
 * Convert FieldDefinition[] into Column[] for DataTable consumption.
 *
 * - Filters by `is_visible` and excludes fields in `hiddenFields`
 * - Sorts by `sort_order`
 * - For `_id` reference fields: resolves to human name via lookupCache
 * - Carries original FieldDefinition on each column for sort/type logic
 */
export function fieldDefsToColumns<T>(
  defs: FieldDefinition[],
  lookupCache: LookupCache,
  hiddenFields: Set<string>,
): FieldDefColumn<T>[] {
  return defs
    .filter((d) => d.is_visible && !hiddenFields.has(d.field_name))
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((def) => {
      const lookupTable = LOOKUP_TABLE_MAP[def.field_name]

      // For reference fields (_id), resolve via lookup cache
      if (lookupTable) {
        const items = lookupCache[lookupTable] ?? []
        return {
          key: def.field_name,
          label: def.display_name,
          fieldDef: def,
          render: (row: T) => {
            const id = (row as Record<string, unknown>)[def.field_name]
            if (id == null) return "\u2014"
            const found = items.find((item) => item.id === Number(id))
            return found?.nazvanie ?? "\u2014"
          },
        }
      }

      return {
        key: def.field_name,
        label: def.display_name,
        fieldDef: def,
      }
    })
}
