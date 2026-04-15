import { ChevronDown, Table2, LayoutGrid } from "lucide-react"
import { ViewSwitcher } from "@/components/shared/view-switcher"
import { cn } from "@/lib/utils"

const viewOptions = [
  { id: "table", label: "Таблица", icon: Table2 },
  { id: "grid", label: "Каталог", icon: LayoutGrid },
]

interface CatalogHeaderProps {
  viewMode: string
  onViewChange: (mode: string) => void
  selectedCollection: string
  onCollectionChange: (collection: string) => void
  collections: string[]
  className?: string
}

export function CatalogHeader({
  viewMode,
  onViewChange,
  selectedCollection,
  onCollectionChange,
  collections,
  className,
}: CatalogHeaderProps) {
  return (
    <div className={cn("flex items-center justify-between gap-4 flex-wrap", className)}>
      <h1 className="text-[22px] font-bold">Каталог моделей</h1>

      <div className="flex items-center gap-2">
        <div className="relative">
          <select
            value={selectedCollection}
            onChange={(e) => onCollectionChange(e.target.value)}
            className="appearance-none flex items-center gap-1.5 px-3 py-1.5 pr-7 bg-bg-soft border border-border rounded-md text-[12px] text-muted-foreground hover:bg-bg-hover hover:text-foreground transition-colors cursor-pointer"
          >
            <option value="">Все коллекции</option>
            {collections.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <ChevronDown
            size={12}
            className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 opacity-50"
          />
        </div>

        <ViewSwitcher options={viewOptions} value={viewMode} onChange={onViewChange} />
      </div>
    </div>
  )
}
