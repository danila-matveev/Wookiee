// Atomic UI компоненты каталога — соответствие MVP wookiee_matrix_mvp_v4.jsx.
// Все стили предполагают .catalog-scope wrapper в parent layout.

export { Tooltip } from "./tooltip"
export type { TooltipPosition } from "./tooltip"

// W9.15 — ellipsis + tooltip-on-overflow для текстовых ячеек таблиц каталога.
export { CellText } from "./cell-text"

export { LevelBadge } from "./level-badge"
export type { Level } from "./level-badge"

export { StatusDot, StatusBadge, CATALOG_STATUSES } from "./status-badge"

export { CompletenessRing } from "./completeness-ring"

export { ColorSwatch } from "./color-swatch"

export { ColorPicker, useAvailableColors } from "./color-picker"
export type { ColorPickerProps } from "./color-picker"

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

// W9.10 — Inline-edit ячейки для /catalog/artikuly и /catalog/tovary.
export { InlineTextCell } from "./inline-text-cell"
export type { InlineTextCellProps } from "./inline-text-cell"
export { InlineColorCell } from "./inline-color-cell"
export type { InlineColorCellProps } from "./inline-color-cell"
export { InlineSelectCell } from "./inline-select-cell"
export type { InlineSelectCellProps, InlineSelectOption } from "./inline-select-cell"
