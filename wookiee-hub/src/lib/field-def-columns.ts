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

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(raw: unknown): string {
  if (raw == null) return "\u2014"
  const str = String(raw)
  try {
    const d = new Date(str)
    if (isNaN(d.getTime())) return str
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })
  } catch {
    return str
  }
}

const DATE_FIELDS = new Set(["created_at", "updated_at"])

// ── Converter ────────────────────────────────────────────────────────────────

/**
 * Convert FieldDefinition[] into Column[] for DataTable consumption.
 *
 * - Filters by `is_visible` and excludes fields in `hiddenFields`
 * - Sorts by `sort_order`
 * - For `_id` reference fields: resolves to human name via lookupCache
 * - For date fields: formats to human-readable DD.MM.YYYY
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

      // For date fields, format to human-readable
      if (def.field_type === "date" || DATE_FIELDS.has(def.field_name)) {
        return {
          key: def.field_name,
          label: def.display_name,
          fieldDef: def,
          render: (row: T) => formatDate((row as Record<string, unknown>)[def.field_name]),
        }
      }

      return {
        key: def.field_name,
        label: def.display_name,
        fieldDef: def,
      }
    })
}
