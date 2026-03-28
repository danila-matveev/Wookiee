import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi } from "@/lib/matrix-api"
import { Skeleton } from "@/components/ui/skeleton"
import { PanelSection } from "./panel-section"
import { PanelFieldRow } from "./panel-field-row"
import { getBackendType, COMPUTED_FIELD_PATTERN, LOOKUP_TABLE_MAP } from "./types"
import type { MatrixEntity } from "@/stores/matrix-store"
import type { FieldDefinition, LookupItem } from "./types"

// ── Inherited field map ─────────────────────────────────────────────────────
/**
 * Fields that are inherited from the parent entity level.
 * They are displayed read-only on child entities with a popover showing parent data.
 */
const INHERITED_FIELDS: Record<string, string[]> = {
  articles: ["kategoriya_id", "kollekciya_id", "fabrika_id", "material", "sostav_syrya"],
  products: [
    "kategoriya_id",
    "kollekciya_id",
    "fabrika_id",
    "material",
    "sostav_syrya",
    "artikul",
  ],
}

// ── Section ordering ─────────────────────────────────────────────────────────
const SECTION_ORDER: Record<string, number> = {
  "Основные": 0,
  "Размеры": 1,
  "Логистика": 2,
  "Контент": 3,
}

function sectionSortKey(sectionName: string | null): number {
  if (!sectionName) return 99
  return SECTION_ORDER[sectionName] ?? 50
}

// ── Section grouping helper ──────────────────────────────────────────────────
function groupFieldsBySection(
  fields: FieldDefinition[],
): Array<{ section: string; fields: FieldDefinition[] }> {
  const map = new Map<string, FieldDefinition[]>()

  for (const field of fields) {
    // Skip invisible and computed fields
    if (!field.is_visible) continue
    if (COMPUTED_FIELD_PATTERN.test(field.field_name)) continue

    const sectionKey = field.section ?? "Другое"
    if (!map.has(sectionKey)) map.set(sectionKey, [])
    map.get(sectionKey)!.push(field)
  }

  // Sort each section's fields by sort_order
  for (const [, sectionFields] of map) {
    sectionFields.sort((a, b) => a.sort_order - b.sort_order)
  }

  // Sort sections by known order, then alphabetically
  return Array.from(map.entries())
    .sort(([a], [b]) => {
      const orderA = sectionSortKey(a)
      const orderB = sectionSortKey(b)
      if (orderA !== orderB) return orderA - orderB
      return a.localeCompare(b, "ru")
    })
    .map(([section, fields]) => ({ section, fields }))
}

// ── Resolve display value for a field ───────────────────────────────────────
function resolveDisplayValue(
  field: FieldDefinition,
  data: Record<string, unknown>,
): unknown {
  // For select fields, try to use the _name counterpart
  if (field.field_type === "select") {
    const nameKey = field.field_name.replace(/_id$/, "_name")
    if (nameKey in data) return data[nameKey]
  }
  return data[field.field_name]
}

// ── Props ────────────────────────────────────────────────────────────────────
interface PanelBodyProps {
  data: Record<string, unknown>
  entityType: string
  isEditing: boolean
  editState?: Record<string, unknown>
  onChange?: (fieldName: string, value: unknown) => void
  lookupCache?: Record<string, LookupItem[]>
  parentData?: Record<string, unknown> | null
  parentEntityType?: string | null
  parentEntityId?: number | null
}

// ── Component ────────────────────────────────────────────────────────────────
export function PanelBody({
  data,
  entityType,
  isEditing,
  editState = {},
  onChange,
  lookupCache = {},
  parentData,
  parentEntityType,
  parentEntityId,
}: PanelBodyProps) {
  const backendEntityType = getBackendType(entityType as MatrixEntity)
  const inheritedFieldNames = INHERITED_FIELDS[entityType] ?? []

  const { data: fields, loading: fieldsLoading } = useApiQuery<FieldDefinition[]>(
    () => matrixApi.listFields(backendEntityType),
    [backendEntityType],
  )

  if (fieldsLoading || !fields) {
    return (
      <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-3/5" />
        <Skeleton className="h-4 w-4/5" />
      </div>
    )
  }

  const sections = groupFieldsBySection(fields)

  if (sections.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        Нет полей для отображения
      </div>
    )
  }

  return (
    <div className="flex-1">
      {sections.map(({ section, fields: sectionFields }) => (
        <PanelSection key={section} title={section} defaultOpen>
          {sectionFields.map((field) => {
            const isInherited = inheritedFieldNames.includes(field.field_name)
            const displayValue = resolveDisplayValue(field, data)

            // Current edit value: use editState when editing, otherwise display value
            const editValue =
              isEditing && field.field_name in editState
                ? editState[field.field_name]
                : displayValue

            // Lookup options for select fields
            const lookupTableName = LOOKUP_TABLE_MAP[field.field_name]
            const lookupOptions = lookupTableName ? lookupCache[lookupTableName] : undefined

            return (
              <PanelFieldRow
                key={field.field_name}
                def={field}
                value={displayValue}
                editValue={editValue}
                isEditing={isEditing}
                lookupOptions={lookupOptions}
                inherited={isInherited}
                parentEntityType={isInherited ? parentEntityType : null}
                parentEntityId={isInherited ? parentEntityId : null}
                parentData={isInherited ? parentData : null}
                onChange={onChange ?? (() => undefined)}
              />
            )
          })}
        </PanelSection>
      ))}
    </div>
  )
}
