// Catalog-local atomic UI — adapters on top of ui-v2 primitives.
// Public API is preserved; under the hood components route to ui-v2.
// .catalog-scope wrapper is gone — stone-50 = DS v2 --color-page (light).

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

export { ColumnsManager } from "./columns-manager"
export type { ColumnDef } from "./columns-manager"

export { RefModal } from "./ref-modal"
export type { RefFieldDef, RefFieldType, RefFieldOption } from "./ref-modal"

export { BulkActionsBar } from "./bulk-actions-bar"
export type { BulkAction } from "./bulk-actions-bar"

export { CommandPalette } from "./command-palette"
export type {
  CommandResult,
  CommandResultCategory,
  SearchGlobalResult,
} from "./command-palette"
