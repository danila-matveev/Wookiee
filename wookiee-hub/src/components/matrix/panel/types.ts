import type { FieldDefinition, LookupItem } from "@/lib/matrix-api"
import type { MatrixEntity } from "@/stores/matrix-store"

// Re-export for panel consumers
export type { MatrixEntity, FieldDefinition, LookupItem }

// ── Constants ────────────────────────────────────────────────────────────────

/**
 * Fields that cannot be edited even in edit mode.
 * These are marketplace-pulled identifiers that are permanently locked once set.
 */
export const IMMUTABLE_FIELDS = new Set([
  "barkod",
  "nomenklatura_wb",
  "ozon_product_id",
  "barkod_gs1",
  "barkod_gs2",
  "ozon_fbo_sku_id",
  "lamoda_seller_sku",
])

/**
 * Pattern for computed join fields (e.g. kategoriya_name).
 * These are derived from FK lookups and should be excluded from edit mode.
 */
export const COMPUTED_FIELD_PATTERN = /_name$/

/**
 * Entity type → title field used in panel header.
 */
export const ENTITY_TITLE_FIELD: Record<string, string> = {
  models: "kod",
  articles: "artikul",
  products: "artikul_ozon",
}

/**
 * Field name → lookup table name for select fields.
 * Used to fetch dropdown options from /api/matrix/lookups/:table.
 */
export const LOOKUP_TABLE_MAP: Record<string, string> = {
  kategoriya_id: "kategorii",
  kollekciya_id: "kollekcii",
  fabrika_id: "fabriki",
  status_id: "statusy",
  cvet_id: "cveta",
  razmer_id: "razmery",
  importer_id: "importery",
}

// getBackendType from entity-registry covers all 9 entity slugs.
// Import and use it directly instead of ENTITY_BACKEND_MAP.
export { getBackendType } from '@/lib/entity-registry'

// ── Interfaces ───────────────────────────────────────────────────────────────

/**
 * Props for a single field row in the panel (read or edit mode).
 */
export interface PanelFieldRowProps {
  def: FieldDefinition
  value: unknown
  editValue: unknown
  isEditing: boolean
  lookupOptions?: LookupItem[]
  onChange: (fieldName: string, value: unknown) => void
}

/**
 * A named group of fields forming a collapsible section in the panel.
 */
export interface PanelSectionData {
  title: string
  fields: FieldDefinition[]
}
