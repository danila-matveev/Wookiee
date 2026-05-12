// Atomic UI компоненты каталога — соответствие MVP wookiee_matrix_mvp_v4.jsx.
// Все стили предполагают .catalog-scope wrapper в parent layout.

export { Tooltip } from "./tooltip"
export type { TooltipPosition } from "./tooltip"

export { LevelBadge } from "./level-badge"
export type { Level } from "./level-badge"

export { StatusDot, StatusBadge, CATALOG_STATUSES } from "./status-badge"

export { CompletenessRing } from "./completeness-ring"

export { ColorSwatch } from "./color-swatch"

export {
  FieldWrap,
  TextField,
  NumberField,
  SelectField,
  StringSelectField,
  MultiSelectField,
  TextareaField,
} from "./fields"
export type { FieldLevel } from "./fields"

export { TagsCombobox } from "./tags-combobox"

export { ColumnsManager } from "./columns-manager"
export type { ColumnDef } from "./columns-manager"

// W9.5 — единый конфигуратор колонок (показать/скрыть/drag + reset + search).
// Применяется ко всем 3 реестрам каталога через `useColumnConfig(pageKey, defaults)`.
export { ColumnConfig } from "./column-config"
export type { CatalogColumnDef } from "./column-config"

export { RefModal } from "./ref-modal"
export type { RefFieldDef, RefFieldType, RefFieldOption } from "./ref-modal"

export { NewModelModal } from "./new-model-modal"

export { BulkActionsBar } from "./bulk-actions-bar"
export type { BulkAction } from "./bulk-actions-bar"

export { CommandPalette } from "./command-palette"
export type {
  CommandResult,
  CommandResultCategory,
  SearchGlobalResult,
} from "./command-palette"

export { AssetUploader } from "./asset-uploader"

export { AttributeControl } from "./attribute-control"

// W8.1 + W8.2 — sortable header + paginator.
export { SortableHeader } from "./sortable-header"
export { Pagination } from "./pagination"
