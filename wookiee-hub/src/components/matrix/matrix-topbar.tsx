import { Search, Settings, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useMatrixStore } from "@/stores/matrix-store"
import { ColumnVisibilityPopover } from "@/components/matrix/column-visibility-popover"
import type { FieldDefinition } from "@/lib/matrix-api"

const entityLabels: Record<string, string> = {
  models: "Модели",
  articles: "Артикулы",
  products: "Товары / SKU",
  colors: "Цвета",
  factories: "Фабрики",
  importers: "Импортёры",
  "cards-wb": "Склейки WB",
  "cards-ozon": "Склейки Ozon",
  certs: "Сертификаты",
}

interface MatrixTopbarProps {
  fieldDefs?: FieldDefinition[]
  hiddenFields?: Set<string>
  onToggleField?: (fieldName: string) => void
  onCreateClick?: () => void
}

export function MatrixTopbar({
  fieldDefs,
  hiddenFields,
  onToggleField,
  onCreateClick,
}: MatrixTopbarProps) {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setSearchOpen = useMatrixStore((s) => s.setSearchOpen)

  return (
    <div className="flex h-12 items-center justify-between border-b border-border px-4">
      <h2 className="text-lg font-semibold">
        {entityLabels[activeEntity] ?? activeEntity}
      </h2>
      <div className="flex items-center gap-2">
        {onCreateClick && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onCreateClick}
            className="gap-1.5 text-muted-foreground"
          >
            <Plus className="h-4 w-4" />
            <span className="text-xs">Создать</span>
          </Button>
        )}
        {fieldDefs && hiddenFields && onToggleField && (
          <ColumnVisibilityPopover
            fields={fieldDefs}
            hiddenFields={hiddenFields}
            onToggle={onToggleField}
          />
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSearchOpen(true)}
          className="gap-1.5 text-muted-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="text-xs">Поиск</span>
          <kbd className="ml-1 rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
            ⌘K
          </kbd>
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
